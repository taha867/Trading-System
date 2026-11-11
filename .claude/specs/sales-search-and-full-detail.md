# Sales Search, Filters & Full Detail — Spec (Backend + Frontend)

> **Status update (2026-11-10): built, and extended.** Added since this spec: exact invoice dropdown, cancelled-invoices panel, sort by date, the same filters on the Other entries tab, and the `insufficient_stock` kind. The purchase side was ported (`PurchaseLogException`).

> **Update (2026-11-11):** the two tabs this spec describes (Invoices and Other entries) were merged into ONE Invoices list: each invoice once (sale + every day-book entry with its number and customer), with "No stock found" lines, bulk lines, corrections and cancellations under it. Backend: `GET /sales/sales-orders/invoices` (`src/sales/invoice_service.py`); frontend: `components/sales/InvoiceList.jsx`.

> **Update (2026-11-11):** Purchase Orders got the same treatment: one Purchases list (`GET /purchasing/purchase-orders/purchases`, `src/purchasing/invoice_service.py`, `components/purchasing/PurchaseList.jsx`) with the payable-only entries under their supplier invoice instead of an Other entries tab.

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This extends the Phase 4 sales screens (`phase-4-backend.md`, `phase-4-frontend.md`) and the September 2026 day-book import work. It has two goals:

1. **Find sales:** search by invoice number, filter by month or date range, customer and item, with a total for whatever you filtered.
2. **Show everything we save:** every column the database stores for a sale (and for the related ledger, stock-lot and day-book exception rows) is visible somewhere on screen.

Status: **proposal, not built.** "Where we stand" was checked against the current code (file and function names given). Anything marked **VERIFY** needs a look at real data before building.

---

## 0. Done when

- On **Sales Orders**, typing an invoice number (or part of it) finds the sale; picking a month shows only that month's sales; picking a customer or item narrows further. A summary line shows *count · total sales · total margin* for exactly what is filtered (all pages, not just the visible one).
- Opening a sale shows the invoice number, customer, sale date, the date it was entered, every line with cost and margin, which stock lots each line drew from (with each lot's received date), and the **ledger entry** it created (date, account, debit, credit).
- A customer's statement shows the invoice number next to each sale and links to it.
- The day-book **"other sales entries"** (bulk batches, corrections, discounts, cancelled invoices) have their own list with the same invoice-number, month and customer filters.
- The **New sales order** form has an optional invoice number field.
- Every database column in section 1.2 appears on a screen (traceability table in section 6).

---

## 1. Where we stand (verified in code)

### 1.1 What is stored today

| Table | Columns | Source |
|---|---|---|
| `sales_order` | `id`, `party_id`, `order_date`, `invoice_number` (nullable text, **not unique, not indexed**), `created_at` | `sales/models.py` |
| `sales_order_line` | `id`, `sales_order_id`, `item_id`, `qty`, `rate_pkr` | `sales/models.py` |
| `sales_order_line_lot` | `id`, `sales_order_line_id`, `stock_lot_id`, `qty_consumed`, `unit_cost_pkr` (landed cost snapshotted at sale time), `created_at` | `sales/models.py` |
| `ledger_entry` (one row per sale) | `entry_date` (= `order_date`), `account` = `"Accounts Receivable"`, `debit` = sale total, `credit` = 0, `reference_type` = `"sales_order"`, `reference_id` = the sale's id, `party_id`, `created_at` | `sales/service.py::create_sales_order`, `ledger/service.py::post_entry` |
| `stock_movement` (one row per lot used) | `stock_lot_id`, `movement_type` = `"sale"`, negative `qty_delta`, `movement_date` = `order_date`, `reason`, `created_at` | `inventory/service.py::consume_stock_fifo` |
| `sales_log_exception` | `id`, `entry_date`, `kind` (`cancelled_invoice` / `bulk_mixed_models` / `blank_model` / `correction` / `discount`), `category_name`, `qty`, `rate_pkr`, `amount_pkr`, `party_id`, `invoice_number`, `note`, `ledger_entry_id`, `created_at` | `sales/models.py`, migration `2026-10-20_add_sales_log_exception.py` |

Order total, line amount, cost and margin are **calculated, not stored** (`SalesOrderRead` computed fields). The sale, its lines, lot rows, ledger row and stock movements are written in **one transaction** (`create_sales_order` ends in a single `commit()`).

### 1.2 What the API returns and what the screens show

| Stored | API (`SalesOrderRead`) | Screen today |
|---|---|---|
| `sales_order.id` | yes | list `#ID`, detail heading |
| `party_id` | yes (id only) | looked up by loading the **whole** parties list (`useParties(LOOKUP_PAGE)`) |
| `order_date` | yes | list, detail |
| **`invoice_number`** | **yes** | **nowhere** |
| **`created_at`** | **yes** | **nowhere** |
| line `qty`, `rate_pkr` | yes | detail table |
| per-lot `stock_lot_id`, `qty_consumed`, `unit_cost_pkr` | yes | detail "Drawn from" column (`Lot #id: qty @ cost`) |
| per-lot `created_at` | no | nowhere |
| the sale's **ledger entry** | **no** | only indirectly on the customer statement |
| `sales_log_exception` (all columns) | **no endpoint at all** | nowhere (only a warning total on the new Reports page) |

### 1.3 What can be searched or filtered today

- `GET /sales/sales-orders` (`sales/router.py::list_sales_orders`) takes **only** `page` and `page_size`. Order is fixed: newest `order_date`, then highest `id`. There is no search, month, customer or item filter, and no total for the filtered set.
- The Sales Orders screen (`components/sales/SalesOrderList.jsx`) has no filter controls. Only Expenses has a server-side filter bar (and the only `<input type="month">`).
- `sales_order.order_date` and `sales_order.invoice_number` have **no database index** (`sales/models.py`).
- The New sales order form (`components/sales/form/SalesOrderForm.jsx`) sends `party_id`, `order_date`, `lines`. **It has no invoice number field**, although `SalesOrderCreate` already accepts one. Only the import scripts fill it.
- The customer statement (`parties/service.py::get_party_statement`, `PartyStatementEntryRead`) shows `reference_type` and `reference_id` but not the invoice number, and the row doesn't link to the sale.

### 1.4 Facts that shape the design

1. **Invoice numbers are not unique by nature.** A day-book correction or discount (`sales_log_exception`) carries the same invoice number as the sale it adjusts. So the database must **not** get a unique constraint (decision in 2.4).
2. **A stock movement can't be tied to one sale.** `stock_movement` has no link to a sale (only `stock_lot_id`, date, qty). The per-lot draw-down already stored in `sales_order_line_lot` is the correct per-sale record, so the detail screen shows that, not movements (decision in 2.6).
3. **A ledger row is linked by reference**, not by foreign key: `ledger_entry.reference_type = 'sales_order'` and `reference_id = sales_order.id`. Payments received later are separate ledger rows (reference `payment_transaction`) tied to the customer, not to one invoice.
4. The list endpoint already loads lines and lot rows for every order on the page (`SALES_ORDER_LOAD_OPTIONS`), so adding embedded names is cheap if done with joins, not with extra queries per row.
5. Precedents to copy: `expenses/service.py::list_expenses` (filters plus a total across all matching rows, `ExpenseListRead.total_amount`), `parties/schemas.py::PartyListRead` (list response with totals), `pagination.py::PaginationParams` (already used as a `Query()` model).

---

## 2. Design decisions

### 2.1 One list endpoint, filters as a validated Pydantic query model

`GET /sales/sales-orders` gains optional filters, declared as one `SalesOrderFilters` Pydantic model used via `Annotated[SalesOrderFilters, Query()]` (same style as `PaginationParams`). All filters are optional and combine with AND:

| Param | Meaning |
|---|---|
| `search` | Text, trimmed. If it is all digits it matches the order `id` **or** an invoice number containing it. Otherwise it matches invoice numbers containing it. Case-insensitive. |
| `party_id` | One customer. |
| `date_from`, `date_to` | Inclusive range on `order_date`. The frontend month picker turns a month into this range. |
| `item_id` | Sales that contain this item (an `EXISTS` subquery on lines, not a join, so rows are never duplicated). |

Validation (model-level, raises 422 through the normal path): `date_from <= date_to`. No maximum span is needed (a paginated list, not a report).

`LIKE` wildcards in `search` (`%`, `_`, `\`) are **escaped**, so searching `50%` or `A_1` finds literal text.

### 2.2 The list response carries totals for the whole filtered set

`SalesOrderListRead(PaginatedResponse[SalesOrderRead])` adds `total_sales_pkr` and `total_margin_pkr`, computed across **every** matching sale (not just the current page), the same idea as `ExpenseListRead.total_amount` and `PartyListRead.total_receivable_pkr`.

- Sales total = `sum(qty × rate_pkr)` over the matching orders' lines.
- Margin = sales total − `sum(qty_consumed × unit_cost_pkr)` over the matching orders' lot rows.
- These are two separate aggregate queries on the same filtered set of order ids (never one join; joining lot rows into the revenue query would multiply revenue by the number of lots a line drew from, as in `reporting/service.py::_revenue_by_item_subquery` / `_cost_by_item_subquery`).

### 2.3 Embed the customer name in the sale

Add `party_name` to `SalesOrderRead` (loaded with a join on a new `SalesOrder.party` relationship, `lazy="raise"` like the other relationships, added to `SALES_ORDER_LOAD_OPTIONS`). The list and detail screens then stop downloading the entire parties list just to turn an id into a name. This follows how `SalesOrderLineRead` already embeds `item_sku`, `model_name`, and so on.

### 2.4 Invoice number: not unique, searchable, and enterable

- **No unique constraint** (1.4 point 1). On create, nothing blocks a duplicate.
- The create form gets an **optional** invoice number field. If a sale with the same number already exists for the same customer, the **UI shows a non-blocking hint** ("Invoice 1234 already exists for this customer — #57"), using the new `search` filter. It never prevents saving.
- Stored value is trimmed; an empty string is saved as `NULL` so "no invoice number" has one representation. Max 64 characters (already enforced by `SalesOrderCreate`; the Yup schema must mirror it per `CLAUDE.md` §3.5).

### 2.5 Indexes (one small migration)

`YYYY-MM-DD_add_sales_search_indexes.py`, one migration for the feature (per `CLAUDE.md` §2.5):

- `sales_order (order_date)`: month filters and ordering.
- `sales_order (invoice_number)`: exact lookups. A plain index does **not** speed up `LIKE '%text%'` (contains) searches; at the current size (hundreds to a few thousand sales) a scan is instant, so a trigram index (`pg_trgm`) is deliberately **not** added now (see risks).
- `sales_log_exception (entry_date)` and `sales_log_exception (party_id)`.

No column is added or changed, so no data migration is needed.

### 2.6 Sale detail = one richer read model, used only by `GET /sales/sales-orders/{id}`

Add `SalesOrderDetailRead(SalesOrderRead)` with extra fields so the list stays light:

- `ledger_entries: list[LedgerEntryRead]`: rows where `reference_type = 'sales_order'` and `reference_id = id` (normally exactly one). `LedgerEntryRead` = `id`, `entry_date`, `account`, `debit`, `credit`, `created_at`. It lives in a new `ledger/schemas.py` (other domains import into `ledger/`, never the reverse; `CLAUDE.md` §2.1).
- Per lot (`SalesOrderLineLotRead`): add `lot_received_date` (from `StockLot.received_date`) through a new read-only `SalesOrderLineLot.stock_lot` relationship, `lazy="raise"`, added to the load options.
- The customer's **current balance** is not embedded (it's a different aggregate); the screen links to the customer statement instead.

**Not shown per sale: stock movements** (1.4 point 2). The lot draw-down is the faithful per-sale record. If a sale-to-movement link is ever wanted, add `sales_order_line_lot_id` to `stock_movement` in a separate, backfilled change; out of scope here.

### 2.7 Day-book "other sales entries" get a read-only list

`GET /sales/sales-log-exceptions` (new), same filter style: `search` (invoice number or note, contains, case-insensitive, wildcards escaped), `kind`, `party_id`, `date_from`, `date_to`. Response `SalesLogExceptionListRead(PaginatedResponse[SalesLogExceptionRead])` plus `total_amount_pkr` for the filtered set and `totals_by_kind`. Read-only for now; there is no create/edit UI (the import scripts own these rows).

`SalesLogExceptionRead` returns every stored column, plus `party_name` (join), `ledger_posted: bool` (`ledger_entry_id is not None`), and the raw `ledger_entry_id`. `kind` is a `Literal` in `sales/constants.py` (add it if it doesn't exist yet) so the schema and the UI labels share one list.

### 2.8 Customer statement shows the invoice number

`PartyStatementEntryRead` gains `invoice_number: str | None`. In `get_party_statement`, collect the `reference_id`s of `reference_type == 'sales_order'` rows, fetch their invoice numbers in **one** query (`WHERE id IN (...)`), and attach them. This avoids a query per row. The frontend renders the number and links to `/sales-orders/:id`.

### 2.9 Filters live in the URL

The list's filters and page are kept in the URL search params (`?search=1234&month=2026-09&party=7`), so a filtered view survives refresh, can be bookmarked or sent, and the browser Back button works. Any filter change resets the page to 1 (same reason as `ExpenseList.jsx::withPageReset`).

---

## 3. Backend spec

All changes in `backend/src/sales/` unless noted. Routers stay thin; logic stays in `service.py` (`CLAUDE.md` §2.2).

### 3.1 Files

| File | Change |
|---|---|
| `sales/constants.py` | `SalesLogExceptionKind = Literal[...]` (5 kinds) if not present |
| `sales/models.py` | `SalesOrder.party` and `SalesOrderLineLot.stock_lot` relationships (`lazy="raise"`); `SalesLogException.party` relationship (`lazy="raise"`) |
| `sales/dependencies.py` | Add the party and stock-lot joins to `SALES_ORDER_LOAD_OPTIONS` (`valid_sales_order` already reuses it) |
| `sales/schemas.py` | `SalesOrderFilters`; `SalesOrderRead.party_name`; `SalesOrderLineLotRead.lot_received_date`; `SalesOrderListRead`; `SalesOrderDetailRead`; `SalesLogExceptionFilters`, `SalesLogExceptionRead`, `SalesLogExceptionListRead`, `SalesLogExceptionKindTotalRead` |
| `ledger/schemas.py` (new) | `LedgerEntryRead` |
| `sales/service.py` | `_order_filter_clauses(filters)`; extend `list_sales_orders`; `get_sales_order_detail`; `list_sales_log_exceptions`; trim/`NULL` normalisation of `invoice_number` in `create_sales_order` |
| `sales/router.py` | Add `SalesOrderFilters` to the list route; `GET /{id}` returns `SalesOrderDetailRead`; new `GET /sales-log-exceptions` route (second router with its own prefix, as in `inventory/router.py`'s `stock_movement_router`) |
| `parties/schemas.py`, `parties/service.py` | `PartyStatementEntryRead.invoice_number`; batched lookup in `get_party_statement` |
| `migrations/versions/YYYY-MM-DD_add_sales_search_indexes.py` | The four indexes in 2.5 |

Route order matters: declare `GET /sales-log-exceptions` on its own router so it can never be captured by `/{sales_order_id}`.

### 3.2 Filter logic (`_order_filter_clauses`)

```
clauses = []
if filters.party_id:   clauses.append(SalesOrder.party_id == filters.party_id)
if filters.date_from:  clauses.append(SalesOrder.order_date >= filters.date_from)
if filters.date_to:    clauses.append(SalesOrder.order_date <= filters.date_to)
if filters.item_id:    clauses.append(exists().where(SalesOrderLine.sales_order_id == SalesOrder.id,
                                                      SalesOrderLine.item_id == filters.item_id))
if filters.search:
    text = escape_like(filters.search.strip())
    contains = SalesOrder.invoice_number.ilike(f"%{text}%", escape="\\")
    clauses.append(or_(SalesOrder.id == int(text), contains) if text.isdigit() else contains)
```

`escape_like` is a small pure helper (in `sales/utils.py`) that escapes `\`, `%`, `_`. The same clauses are used by the count query, the page query, and both total aggregates, so the numbers can never disagree.

### 3.3 Detail loader

`get_sales_order_detail(db, sales_order)` queries `LedgerEntry` where `reference_type = 'sales_order'` and `reference_id = sales_order.id`, ordered by `entry_date, id`, and returns a `SalesOrderDetailRead` built from the already-loaded sale plus those rows. Read-only: no `commit()`.

### 3.4 Errors

- Bad date range (`date_from > date_to`) → 422 through Pydantic validation.
- Unknown `party_id`/`item_id` in a filter is **not** an error: it returns an empty list (a filter that matches nothing).
- Unknown sale id → existing `SalesOrderNotFound` (404).

### 3.5 Backend checks

The repo has no `backend/tests/` directory, so verify through the API docs and a throwaway script (adding a test setup is out of scope unless you ask). Cases:

1. `search` with a full invoice number, a partial one, mixed case, and with `%` / `_` (must match literally).
2. `search` that is all digits matches both an order `id` and invoice numbers containing it.
3. A month range includes the first and last day, excludes the day before and after.
4. `party_id`, `item_id` and combinations (AND). `item_id` returns each sale **once** even if it has several matching lines.
5. `total_sales_pkr` and `total_margin_pkr` equal the sum over **all** pages for the same filter, and equal the sum of the visible rows when everything fits on one page.
6. Totals reconcile with the Reports page and Margin by Item for the same dates (gross profit for a month = the month filter's margin total).
7. Detail returns one ledger entry whose `debit` equals `total_pkr` and whose `entry_date` equals `order_date`.
8. Party statement rows for sales carry the right invoice number; one query is used for the lookups.
9. No change in results when no filter is sent (default list unchanged).

---

## 4. Frontend spec

Layering per `CLAUDE.md` §3.4: component → hook → service → `fetchClient`. Use the `frontend-design-system` skill for visuals. Follow the existing Expenses filter bar and Card/Table conventions.

### 4.1 Files

| File | Change |
|---|---|
| `services/salesService.js` | `listSalesOrders(params)` already uses `buildQueryString` (it drops empty filters); add `listSalesLogExceptions(params)` |
| `utils/queryKeys.js` | add `salesLogExceptionKeys` (`all`, `lists`, `list(params)`) beside `salesOrderKeys` |
| `hooks/salesHooks/salesQueries.js` | add `useSalesLogExceptions(params)`; both list hooks use `placeholderData: keepPreviousData` so typing doesn't flash the table |
| `hooks/useDebouncedValue.js` (new) | small generic hook (like `useImperativeDialog.js`), 400 ms |
| `utils/dateUtils.js` | already has `monthBounds`, `currentMonth`, `monthLabel` (from the Profit & Loss work); add `formatDateTime(iso)` for `created_at` |
| `utils/constants.js` | `SALES_LOG_EXCEPTION_KIND_LABELS` (plain-English names) |
| `validations/salesSchemas.js` | `invoice_number: string().trim().max(64).nullable()` mirroring the backend |
| `components/sales/form/SalesOrderForm.jsx` | optional "Invoice number" `FormField`; send `invoice_number` (empty → omitted); duplicate hint (see 4.4) |
| `components/sales/SalesOrderList.jsx` | filter bar, new columns, summary bar |
| `components/sales/SalesOrderDetail.jsx` | all saved fields, lot dates, ledger card |
| `components/sales/SalesLogExceptionList.jsx` (new) | the "Other entries" list |
| `containers/SalesOrdersContainer.jsx` | `Tabs`: **Invoices** and **Other entries** (existing `ui/tabs`), tab in the URL (`?tab=other`) |
| `components/parties/PartyStatement.jsx` | show invoice number, link sale rows to `/sales-orders/:id` |
| `components/reporting/ProfitLossStatement.jsx` | make the "sales without item data" warning link to Other entries for that month |

### 4.2 Sales Orders list

**Filter bar** (grid `grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4`, same markup as `ExpenseList.jsx`), above the table:

1. **Search**: text input, placeholder "Invoice number or #ID", debounced 400 ms, with a clear (×) button.
2. **Customer**: `FormSelect`, options from `useCustomerParties()`, with an "All customers" entry (`ALL` sentinel).
3. **Month**: `<input type="month">` (empty = all time). Picking a month sets `date_from`/`date_to` via `monthBounds`.
4. **Item**: the existing `ItemCombobox` (from `components/custom`), clearable.

A **Clear filters** button appears when any filter is active. Filters sit in the URL (2.9).

**Summary bar** (copy of the Expenses summary box): `₨ total sales` large, then "N sales · margin ₨X" and, when filtered, "matching the filters below". Values come from `total_sales_pkr`, `total` and `total_margin_pkr` of the response, so they cover every page.

**Table columns** (all inside `overflow-x-auto rounded-lg border`, CLAUDE.md §3.7):

| Column | From |
|---|---|
| **Invoice no.** (`—` if none) | `invoice_number` |
| ID (link to detail) | `id` |
| Customer (link to the customer statement) | `party_name`, `party_id` |
| Sale date | `order_date` |
| Entered on | `created_at` (date and time, local) |
| Total PKR | `total_pkr` |
| Margin PKR (red if negative) | `total_margin_pkr` |
| Margin % | derived display-only from the two server values, like `MarginReportTable` |

Below `sm`, collapse each row into a stacked card showing **invoice no., customer, date and total** first. Empty state distinguishes "no sales yet" from "no sales match these filters".

### 4.3 Sales Order detail: every saved field visible

- **Header block** (a labelled definition list): Invoice number, Sale ID, Customer (link), Sale date, **Entered on** (`created_at`), Total, Total margin.
- **Lines table** (existing) plus: category (already in `lineItemLabel`), Cost and Margin per line (existing), and in "Drawn from": `Lot #id · received DATE · qty @ unit cost` (uses `lot_received_date`). Lot id links to the Inventory lot view if that route exists (**VERIFY**), otherwise plain text.
- **"Posted to ledger" card**: for each entry in `ledger_entries`: Date, Account, Debit, Credit, "Entered on" (`created_at`), and a one-line explanation, "Added ₨X to what this customer owes." Link "View customer statement".
- A note under Drawn from: "Cost is the landed cost of the lot at the time of sale."
- On phones the header block stacks and the ledger card sits below the lines.

### 4.4 New sales order form

- Optional **Invoice number** `FormField` next to Customer and Date (single column below `md`).
- After typing a non-empty value, a debounced `useSalesOrders({ search, party_id })` call powers the **non-blocking hint** "Invoice 1234 already exists for this customer (#57)" with a link. The hint never disables Save.
- Empty or whitespace-only → not sent (backend stores `NULL`).

### 4.5 Other entries (day-book exceptions) list

Read-only table in a Card, filters: **Search** (invoice number or note), **Kind** (`FormSelect` from `SALES_LOG_EXCEPTION_KIND_LABELS`), **Customer**, **Month**. Summary: total amount and a small per-kind breakdown.

Columns: Date, Kind (badge, plain-English label), Invoice no., Customer, Category, Qty, Rate, Amount, Note, **Ledger** ("Posted" / "Not posted", a cancelled invoice has none), Entered on. A short explainer above the table: "Sales that couldn't be matched to specific items (bulk batches, price corrections, discounts, cancelled invoices). They change what a customer owes but not your stock, and are not in monthly profit by default."

### 4.6 Customer statement

Reference column shows `Sale #57 · Invoice 1234` (link to the sale) for sales rows, and keeps the existing text for payments and others.

### 4.7 Frontend checks

- `npm run lint` and `npm run build` pass.
- At 375 / 768 / 1280 px: filter bar stacks, table scrolls or becomes cards, summary bar wraps, detail blocks stack.
- Search a real invoice number (try one imported from the September day book), then a partial one; pick a month and check the summary equals the Reports page revenue for that month.
- Refresh and Back with filters set; filters persist from the URL.
- Create a sale with and without an invoice number; duplicate hint appears and does not block.
- Open one imported sale and one hand-entered sale; compare each detail field with the database row (6).

---

## 5. Phasing

1. **Backend, list:** schemas, filters, totals, `party_name`, indexes migration. Verify through the API docs.
2. **Backend, detail and extras:** ledger entries on detail, lot received date, other-entries endpoint, statement invoice number.
3. **Frontend, list and form:** filter bar, summary, columns, invoice field and duplicate hint.
4. **Frontend, detail, other entries, statement, Reports link.**
5. **Reconcile with real data** (section 3.5 points 5–7 and 4.7), then commit.
6. **Later, optional (section 7):** purchase-order parity, trigram search, sale-to-movement link.

---

## 6. Traceability: every saved field has a place on screen

| Stored (table.column) | Shown where |
|---|---|
| `sales_order.id` | list ID column, detail header |
| `sales_order.party_id` | customer name (link) in list, detail, statement |
| `sales_order.order_date` | list, detail; month filter |
| `sales_order.invoice_number` | list column, detail header, search, form field, statement |
| `sales_order.created_at` | list "Entered on", detail header |
| `sales_order_line.item_id`, `qty`, `rate_pkr` | detail lines; item filter |
| `sales_order_line_lot.stock_lot_id`, `qty_consumed`, `unit_cost_pkr` | detail "Drawn from"; cost and margin |
| `sales_order_line_lot.created_at` | not shown (same instant as the sale's `created_at`; deliberately omitted) |
| `stock_lot.received_date` (for each lot used) | detail "Drawn from" |
| `ledger_entry.entry_date`, `account`, `debit`, `credit`, `created_at` | detail "Posted to ledger" card |
| `ledger_entry.reference_type`, `reference_id` | the link that builds that card; statement reference column |
| `stock_movement.*` for sales | not shown per sale (no link to a sale, see 1.4 point 2); the lot draw-down covers it. Movements stay visible on the Inventory screens |
| `sales_log_exception.entry_date`, `kind`, `category_name`, `qty`, `rate_pkr`, `amount_pkr`, `party_id`, `invoice_number`, `note`, `ledger_entry_id`, `created_at` | Other entries list (every column; `ledger_entry_id` shown as Posted / Not posted) |

---

## 7. Optional later work

- **Purchase orders** also store `invoice_number` and show it nowhere. Same treatment: column, search box, field on the form, month filter. Mirror this spec in `purchasing/` once sales is done.
- **Sort options** (by total, margin, invoice number) on the list.
- **Trigram index** (`pg_trgm`) for fast "contains" search if the sales table grows past roughly 100k rows.
- **Link a sale to its stock movements** via a foreign key (needs a backfill for existing sales).
- **Create/edit UI for day-book exceptions** if you ever enter them by hand.
- **Export** the filtered list (CSV), reusing the filters.

---

## 8. Risks and open questions

| # | Question / risk | Impact | Resolve by |
|---|---|---|---|
| 1 | Should invoice numbers be unique per customer? The day book reuses a number for corrections, so this spec says no | Duplicates possible | Confirm with the owner how the paper numbers behave |
| 2 | How are imported invoice numbers formatted (leading zeros, prefixes, spaces)? | "Contains" search should still find them; exact-match expectations may differ | `SELECT invoice_number FROM sales_order WHERE invoice_number IS NOT NULL LIMIT 50` (needs your OK to run) |
| 3 | The `search` digits rule matches order `id` **and** invoice text, so "12" may return both sale #12 and invoice 112 | Slightly broad results | Accept (ordered newest first); or add an explicit "ID" mode later |
| 4 | `item_id` filter plus totals on large data | Query cost | Fine at current size; `EXISTS` is index-friendly (`sales_order_line.item_id` is already indexed) |
| 5 | Timezone: `created_at` is stored with timezone; the browser shows local time. Order dates are plain dates | None expected | Check once with a sale entered late evening |
| 6 | Role limits: once multi-user exists (`MULTI_USER_ANALYSIS.md`), margin columns may need to be hidden from staff | Sensitive profit data | Gate margin fields by role at that point |
| 7 | The migration adds indexes to live tables | Brief lock on large tables | Tiny tables today; run in a quiet moment |

---

## 9. Acceptance criteria

- [ ] `GET /sales/sales-orders` supports `search`, `party_id`, `date_from`, `date_to`, `item_id`; combined filters AND together; default behaviour unchanged.
- [ ] The response includes `total_sales_pkr` and `total_margin_pkr` over all matching sales, and they reconcile with the Reports page for the same dates.
- [ ] Searching an imported invoice number (full or part) finds the sale; `%` and `_` search as literal characters.
- [ ] The list shows Invoice no., Customer name, Sale date, Entered on, Total and Margin without downloading the whole parties list.
- [ ] The detail page shows every field in section 6, including each lot's received date and the ledger entry.
- [ ] The New sales order form has an optional invoice number; empty saves as `NULL`; duplicates only show a hint.
- [ ] The Other entries list shows every `sales_log_exception` column with kind, customer, month and invoice filters.
- [ ] Customer statement sale rows show the invoice number and link to the sale, using one batched lookup.
- [ ] Filters persist in the URL; changing a filter resets to page 1.
- [ ] Mobile layouts verified at 375 / 768 / 1280 px; money stays `Decimal` server-side and goes through `CurrencyAmount`.
- [ ] No unique constraint added; one migration adds the four indexes; no data changed.

---

## 10. Implementation notes (deviations from this spec, found while reading the code)

1. **Filters use `Annotated[PaginationParams, Depends()]` plus plain scalar query params**, not a Pydantic query model (section 2.1). FastAPI 0.141 stops flattening a Query model when any other query param is present (see `crud.py` and `inventory/router.py::list_stock_lots`). The `date_from <= date_to` rule is checked in the service and raises `InvalidSalesFilter` (422).
2. **`ledger/schemas.py::LedgerEntryRead` already existed**, so it is reused, not created.
3. **Statement invoice numbers (section 2.8):** `parties/` must not import `sales/`, so `get_party_statement` is unchanged. Sales owns a batched lookup, `GET /sales/sales-orders/invoice-numbers?ids=1&ids=2` (repeated `ids`, max 500), and `PartyStatement.jsx` calls it for the sale rows via `useInvoiceNumbers`.
4. **Search debounce:** the repo's `useDebouncedValue` is reused for the form's duplicate hint. The list screens use a new generic `hooks/useSearchParamFilters.js` that keeps filters and page in the URL and debounces in the change handler (no effect), so clearing filters can't be raced by a stale pending write.
5. **No lot detail page exists**, so lot ids in "Drawn from" are plain text, not links.
6. **Reports link:** the Profit & Loss warnings are plain strings, so a separate "View the sales without item data" link is shown when `unitemised_sales_pkr` is non-zero.
7. **Item filter totals** cover whole sales that contain the chosen item, and the summary bar says so.
8. The `item_id` `EXISTS` subquery uses an **aliased** line table; an un-aliased one would auto-correlate with the totals queries' own `sales_order_line` and silently change meaning.
