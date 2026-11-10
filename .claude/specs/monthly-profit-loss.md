# Monthly Profit & Loss Report — Spec (Backend + Frontend)

> **Status update (2026-11-10): built.** The P&L is implemented (`backend/src/reporting`, `ProfitLossStatement.jsx`) with per-line rounding. By default it excludes sales-log lines of kind `insufficient_stock` (231 rows, ₨540,510), so September revenue is understated until they are replayed or treated as revenue.

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This is a cross-cutting feature on top of Phase 8 (`phase-8-backend.md`, `phase-8-frontend.md`): it adds a **calendar-month profit & loss statement** (revenue − cost of goods − stock losses − expenses = net profit), which the app does not have today. No new transactional tables are needed. The feature reads data phases 1–7 already write.

Status of this document: **proposal, not built.** Every statement under "Where we stand" was checked against the current code (file and function names given). Anything marked **VERIFY** must be checked against real data or code before implementation starts.

---

## 0. The question this answers

> "If a user wants to check profit/loss monthly, or the balance statement, showing profit based on what the buying cost was and what things were sold for — does our app do this?"

**Answer today: partly.** Per-sale profit on landed cost is correct and stored. Nothing rolls it up by calendar month, and nothing subtracts expenses or stock losses. There is no net profit figure anywhere.

**Done when:** a user picks a month (e.g. October 2026) on a Reports screen and sees, on one screen: sales revenue, cost of goods sold (landed cost, FIFO), gross profit and margin %, stock losses, expenses by category, and net profit, with last month beside it for comparison. Every figure must reconcile with the existing sales-order, margin and expense screens.

---

## 1. Where we stand (verified in code)

### 1.1 What already works

| Capability | Where | Notes |
|---|---|---|
| Landed cost per unit | `cargo/service.py` (allocation sets `PurchaseOrderLine.landed_cost_pkr = rate_pkr + allocated_cost/qty`); `inventory/service.py` receive copies it to `StockLot.landed_cost_pkr` | `rate_pkr` is the RMB rate snapshotted at PO creation, so history is stable |
| Cost of goods stored at sale time | `sales/models.py` `SalesOrderLineLot(qty_consumed, unit_cost_pkr)`; written by `sales/service.py` via `inventory.consume_stock_fifo` | FIFO, oldest lot first, with row locks. Later changes to a lot cannot change an old sale's cost |
| Per-order margin | Sales order list and detail screens (`total_margin_pkr`, per-line cost and margin, lot draw-down) | Order level only |
| Gross margin report | `reporting/service.py::get_margin_report`, `GET /reporting/margin?window_days=` | Revenue = `sum(qty × rate_pkr)`, cost = `sum(qty_consumed × unit_cost_pkr)`, both filtered on `SalesOrder.order_date`. Per item with a total row |
| Balance statement | `reporting/service.py::get_balance_statement`, `GET /reporting/balance-statement` | Cash by account + receivables − payables + inventory at landed cost = "net position". Today only |
| Month-filtered expense total | `expenses/service.py::list_expenses` (`expense_date_from/to`, `total_amount`); frontend `ExpenseList.jsx` has the only `<input type="month">` | See 1.3 point 6 about drafts |

### 1.2 What is missing

1. **No calendar-month filter anywhere in `src/reporting`.** Every endpoint takes one `window_days` (1–730), always measured back from `date.today()` (`reporting/constants.py`, `reporting/router.py`, `get_margin_report` lines computing `start_date = end_date - timedelta(days=window_days)`). "Last 30 days" is not "October".
2. **No profit & loss.** Revenue, COGS and expenses are never shown together. The words "profit" and "net profit" do not appear in the UI.
3. **Expenses are in no report.** `get_margin_report` does not touch `Expense`.
4. **Stock losses are never valued.** `inventory/service.py::create_adjustment` and `mark_stock_lot_damaged` change `qty_remaining` and write a `StockMovement` row (`movement_type` = `adjustment` or `damaged`, `qty_delta`) but post no ledger entry and store no cost.
5. **The balance statement cannot be viewed for a past date.** It only supports `as_of = date.today()` (`BalanceStatementRead.as_of`).
6. **No export or print of any financial figure.** `StockListShare.jsx` (stock list image/HTML) is the only share/export feature.

### 1.3 Things that would make a naive profit report wrong

These are the reason the design in section 2 reads the domain tables, not the ledger.

1. **The ledger is not a P&L ledger.** `ledger/models.py` is single-sided rows (`entry_date`, free-text `account`, `debit`, `credit`). Postings found (`post_entry` callers):
   - Purchase order → credit "Accounts Payable" for `qty × rate_pkr` (no freight)
   - Sales order → debit "Accounts Receivable" for the total (no revenue account, no cost-of-goods entry, no credit to Inventory)
   - Stock receipt → debit "Inventory" at landed cost (never credited when stock is sold)
   - Payments, opening balances → account legs and optional AR/AP legs
   - Expenses → no direct posting; `expenses/service.py::_post_expense_payment` creates a `PaymentTransaction` (direction `out`, no party) that posts one cash credit

   So `GROUP BY account` on the ledger gives cash, receivables, payables and an ever-growing "Inventory" debit — **not revenue, cost or expenses.** `PLAN.md` Phase 8 assumed the ledger would carry this; in practice it does not.
2. **Cargo cost never reaches the ledger.** `cargo/service.py` has no `post_entry` call. Freight only raises `landed_cost_pkr`. This is fine for the P&L (cost of goods already includes freight through the lot cost) but means a ledger-derived cost would be wrong.
3. **The ledger and the balance statement disagree on inventory.** The statement values inventory from `StockLot` (`qty_remaining × landed_cost_pkr`), not from the "Inventory" ledger account. The statement is right; the ledger account is not usable.
4. **Expense double counting trap.** A confirmed expense exists both as an `expense` row and as a cash `LedgerEntry`/`PaymentTransaction`. A P&L must read **one** of them. This spec reads the `expense` table.
5. **Unitemised sales are outside the sales chain.** `sales/models.py::SalesLogException` (kinds: `cancelled_invoice`, `bulk_mixed_models`, `blank_model`, `correction`, `discount`) holds sale-like events with no item. They post an Accounts Receivable ledger entry but have no `SalesOrderLine` and no cost. Revenue from `SalesOrderLine` therefore **understates** sales if these carry real money, and their cost is unknown.
6. **Expense totals include drafts.** `list_expenses` applies no default status filter, so `total_amount` sums `draft` (unpaid recurring proposals) and `confirmed` rows unless `status` is passed. For profit, only `confirmed` counts.
7. **Opening balances are dated the day they were entered.** Party and payment-account opening balances are posted with `entry_date = date.today()` at creation (`parties/service.py`, `payments/service.py`). They are not business-dated, so any as-of-past-date ledger report would be wrong. This only matters for the Phase 2 as-of balance statement (section 5).
8. **No returns, no discount field.** There is no sales return, purchase return or credit note model. Discounts exist only as `SalesLogException(kind="discount")` from the day-book import.
9. **`GET /reporting/reorder-priority` writes to the database** (`recalculate_reorder_priority` sets `Model.priority` and commits). A read verb with a side effect. Out of scope here, noted so the new endpoint does not copy it.
10. **Stale comment:** `payments/service.py` near `get_account_balances` still says `get_party_statement` double counts opening balances; the code excludes that reference type (`parties/service.py`). The comment is out of date.

---

## 2. Design decisions

### 2.1 Build the P&L from domain tables, not from the ledger

Revenue from `sales_order_line`, cost from `sales_order_line_lot`, stock losses from `stock_movement` + `stock_lot`, expenses from `expense`. Reasons: (a) these are the sources of truth and are already correct; (b) fixing the ledger to carry revenue/COGS/expense accounts would change every posting path, break historical consistency, and require a backfill; (c) the existing Margin report already works this way, so the new report reconciles with it by construction.

The ledger improvements (revenue / COGS / expense accounts, crediting Inventory on sale) are **deferred** (section 7). They are bookkeeping hygiene, not needed for a correct P&L.

### 2.2 Accrual basis, with the date of each source stated explicitly

| Line | Source | Date column used |
|---|---|---|
| Revenue | `SalesOrderLine.qty × rate_pkr` | `SalesOrder.order_date` |
| Cost of goods sold | `SalesOrderLineLot.qty_consumed × unit_cost_pkr` | `SalesOrder.order_date` (same as revenue, so revenue and cost always land in the same month) |
| Stock loss / gain | `StockMovement` of type `damaged` or `adjustment`, valued at `StockLot.landed_cost_pkr` | `StockMovement.movement_date` |
| Expenses | `Expense.amount` where `status = 'confirmed'` | `Expense.expense_date` |

Money received from customers and paid to vendors is **not** profit or loss and is excluded (it moves cash, receivables and payables). Purchases are excluded too: buying stock is an asset (inventory); it only becomes cost when sold (COGS) or lost (stock loss). Freight is already inside the lot cost.

### 2.3 Net profit formula

```
revenue                      = sum(qty * rate_pkr) for lines in period
cogs                         = sum(qty_consumed * unit_cost_pkr) for those lines' lots
gross_profit                 = revenue - cogs
gross_margin_pct             = gross_profit / revenue * 100   (0 if revenue = 0)
stock_loss                   = sum(-qty_delta * lot.landed_cost_pkr) for 'damaged' and 'adjustment' movements in period
                               (positive = loss; a positive qty_delta adjustment reduces it)
expenses_total               = sum(amount) of confirmed expenses in period
net_profit                   = gross_profit - stock_loss - expenses_total
```

`receipt` and `sale` movements are never in `stock_loss` (receipts add stock; sales are already in COGS).

### 2.4 Unitemised sales are shown as a separate, clearly flagged line — not silently added

`SalesLogException` rows have no cost, so adding them to revenue would overstate gross profit. Decision: return them as **`unitemised_sales`** (sum of `amount_pkr` in the period, by `entry_date`, with a per-kind breakdown) and **do not** include them in `revenue` or `net_profit` by default. The response carries a `warnings` list when this figure is non-zero, and the UI shows it as "Sales without item/cost data (not in profit)". A boolean query flag `include_unitemised` (default `false`) adds them to revenue with zero cost for users who want the cash-realistic view.

> **VERIFY before building:** run `SELECT kind, count(*), sum(amount_pkr) FROM sales_log_exception GROUP BY kind` against the real database. If `amount_pkr` is signed (discounts negative) or if `bulk_mixed_models` rows represent real stock that left the shelf, the default above may need to change. Also confirm whether stock for those events was deducted by hand with `adjustment` movements (then it already appears as stock loss and would double count against unitemised revenue).

### 2.5 Period parameters

`GET /reporting/profit-loss` takes `date_from` and `date_to` (both inclusive `date`), not `month`. The frontend month picker converts a month to a range (same pattern as `ExpenseList.jsx::monthToDateRange`). This keeps the endpoint usable for quarters, custom ranges and year to date later without another endpoint.

- Validation (Pydantic/`Query`): `date_from <= date_to`; range at most 366 days; `date_to` may not be in the future more than the current date is — **VERIFY** whether future-dated sales exist; if so, drop this rule.
- `compare_previous: bool = False` — when true the response includes a `previous` block for the immediately preceding period of the **same length and alignment** (for a full calendar month, the previous calendar month; otherwise the same number of days directly before `date_from`).

### 2.6 Calendar-aware server date

`date.today()` is server-local. If the server runs in UTC and the business is in Lahore (UTC+5), "today" is wrong for the first five hours of each local day. The new endpoint avoids `date.today()` entirely (the client sends both dates). This does not fix the existing endpoints; it only avoids adding to the problem. **VERIFY** the server timezone for the existing "as of today" balance statement.

### 2.7 Money and typing

All amounts are `Decimal`, quantised with the existing `money()` helper used by `reporting/service.py`. `margin_pct` follows the existing precedent (`MarginReportEntryRead.margin_pct: float`, with the comment that it is a ratio, not currency).

### 2.8 No schema change, no migration (v1)

All needed columns exist. **Optional performance index:** `sales_order.order_date` and `expense.expense_date` are not indexed (`sales/models.py` has `order_date` with no `index=True`; `expenses/models.py` likewise). With the current data volume a sequential scan is fine. Add the indexes only if the report is measurably slow, as one small migration named `YYYY-MM-DD_add_report_date_indexes.py`, following the naming convention in `CLAUDE.md` section 2.5.

---

## 3. Backend spec

Everything lives in the existing `backend/src/reporting/` package. No new package.

### 3.1 Endpoint

```
GET /reporting/profit-loss
  query:
    date_from: date            (required)
    date_to: date              (required)
    compare_previous: bool     (default false)
    include_unitemised: bool   (default false)
  auth: Depends(get_current_user)
  response_model: ProfitLossRead
```

Router function stays under ~10 lines: build the params, call `service.get_profit_loss(db, ...)`, return. Validation of the date range raises a domain exception (`InvalidReportPeriod`, 422) translated by the existing `AppException` handler; it must not be an `HTTPException` in the service.

### 3.2 Schemas (`reporting/schemas.py`)

```python
class ExpenseCategoryTotalRead(BaseModel):
    category_id: int
    category_name: str
    frequency: str            # "daily" | "monthly", from ExpenseCategory
    total_pkr: Decimal

class UnitemisedSalesKindRead(BaseModel):
    kind: str
    count: int
    total_pkr: Decimal

class ProfitLossPeriodRead(BaseModel):
    date_from: date
    date_to: date
    revenue_pkr: Decimal
    cogs_pkr: Decimal
    gross_profit_pkr: Decimal
    gross_margin_pct: float
    stock_loss_pkr: Decimal                       # positive = net loss
    expenses_total_pkr: Decimal
    expenses_by_category: list[ExpenseCategoryTotalRead]
    net_profit_pkr: Decimal
    net_margin_pct: float                         # net_profit / revenue * 100
    units_sold: Decimal
    order_count: int
    unitemised_sales_pkr: Decimal
    unitemised_sales_by_kind: list[UnitemisedSalesKindRead]
    draft_expenses_pkr: Decimal                   # excluded from profit, shown so nothing is hidden

class ProfitLossRead(BaseModel):
    current: ProfitLossPeriodRead
    previous: ProfitLossPeriodRead | None
    warnings: list[str]
```

`previous` is `None` unless `compare_previous=true`.

### 3.3 Service logic (`reporting/service.py::get_profit_loss`)

Build one private function `_compute_period(db, date_from, date_to, include_unitemised) -> ProfitLossPeriodRead` and call it once for `current` and, if requested, once for `previous`. No raw SQL; async SQLAlchemy, same style as `get_margin_report`.

1. **Revenue and units, order count**
   `select(sum(SalesOrderLine.qty * SalesOrderLine.rate_pkr), sum(SalesOrderLine.qty), count(distinct SalesOrder.id))` joined `SalesOrderLine → SalesOrder`, filtered `SalesOrder.order_date BETWEEN date_from AND date_to`.
2. **COGS**
   `select(sum(SalesOrderLineLot.qty_consumed * SalesOrderLineLot.unit_cost_pkr))` joined `SalesOrderLineLot → SalesOrderLine → SalesOrder`, same date filter.
   Revenue and COGS must come from separate aggregate queries (not one join) to avoid multiplying `qty × rate_pkr` by the number of lot rows per line — this is the same reason `get_margin_report` uses two subqueries.
3. **Stock loss**
   `select(sum(-StockMovement.qty_delta * StockLot.landed_cost_pkr))` from `StockMovement` joined `StockLot`, where `movement_type IN ('damaged','adjustment')` and `movement_date BETWEEN ...`. Use `coalesce(..., 0)`.
4. **Expenses**
   Total and per-category: `select(Expense.category_id, ExpenseCategory.name, ExpenseCategory.frequency, sum(Expense.amount))` joined `ExpenseCategory`, where `status = 'confirmed'` and `expense_date BETWEEN ...`, grouped by category, ordered by total descending. Also compute `draft_expenses_pkr` with `status = 'draft'` in the same range.
5. **Unitemised sales**
   `select(SalesLogException.kind, count(), sum(amount_pkr))` where `entry_date BETWEEN ...`, grouped by `kind`. If `include_unitemised`, add the total to `revenue_pkr` (cost stays 0) and add a warning that gross profit is overstated by that amount's unknown cost.
6. **Derived values** — compute in Python from the Decimal sums per section 2.3. Guard division by zero for both margin percentages.
7. **Warnings** (strings, not errors), for example:
   - `"N draft expense(s) totalling X are not included."` when `draft_expenses_pkr > 0`.
   - `"X of sales without item/cost data is not included in profit."` when unitemised is non-zero and `include_unitemised` is false.
   - `"M sale line(s) in this period have no recorded cost."` when any `SalesOrderLine` in the period has no `SalesOrderLineLot` rows (a data-integrity signal; the existing margin report silently treats such cost as 0).
8. **Read-only.** No `commit()`, no writes.

### 3.4 Relationship to the existing margin report

`get_profit_loss.current.gross_profit_pkr` for a period must equal `get_margin_report`'s `total_margin_pkr` over the same dates (given the margin report can only express rolling windows, compare using a window that matches). To make this enforceable, extract the revenue/COGS aggregation into one shared private helper used by both so they cannot drift apart.

### 3.5 Files touched (backend)

| File | Change |
|---|---|
| `reporting/schemas.py` | Add the schemas in 3.2 |
| `reporting/service.py` | Add `get_profit_loss`, `_compute_period`, shared revenue/COGS helper |
| `reporting/router.py` | Add the `/profit-loss` route |
| `reporting/exceptions.py` (new) | `InvalidReportPeriod(AppException)` 422, per the domain-package convention in `CLAUDE.md` 2.1 |
| `reporting/constants.py` | `MAX_REPORT_RANGE_DAYS = 366` |
| `main.py` | none (router already mounted) |
| migrations | none in v1 (optional index migration, 2.8) |

### 3.6 Backend tests

The repo has no `backend/tests/` directory today. Tests are not part of the established workflow; if the team wants them, create `backend/tests/reporting/` and use a real Postgres (the repo's `docker-compose.yml`), not SQLite, because the report relies on `Numeric` behaviour. Minimum cases:

1. One order, one lot: revenue, COGS and gross profit match hand calculation.
2. One line drawing from **two lots at different costs** (FIFO): COGS equals the sum of both slices, revenue is not doubled.
3. Order on the first and last day of the month are included; the day before and after are excluded.
4. Confirmed vs draft expenses: drafts excluded from net profit, included in `draft_expenses_pkr`.
5. `damaged` movement valued at the lot cost; positive `adjustment` reduces stock loss; `receipt` and `sale` movements ignored.
6. Empty period: all zeros, no division error.
7. `date_from > date_to` and range over 366 days → 422.
8. `compare_previous` returns the correct previous calendar month, including across a year boundary and for February.
9. Reconciliation: `gross_profit_pkr` equals `get_margin_report().total_margin_pkr` for the same data.

---

## 4. Frontend spec

Follows the existing layering (`CLAUDE.md` section 3.4): component → `reportingQueries.js` → `reportingService.js` → `fetchClient`. Use the `frontend-design-system` skill for the visual design before writing JSX.

### 4.1 New and changed files

| File | Change |
|---|---|
| `services/reportingService.js` | Add `getProfitLoss({ dateFrom, dateTo, comparePrevious, includeUnitemised })`. Build the query with `URLSearchParams` like the other reporting calls; do **not** use `buildQueryString` (it injects `page`/`page_size`, as the comment at the top of the file explains) |
| `utils/queryKeys.js` | Add `reportingKeys.profitLoss(from, to, compare, unitemised)` |
| `hooks/reportingHooks/reportingQueries.js` | Add `useProfitLoss(params)` |
| `utils/dateUtils.js` (new) or `utils/currencyUtils.js` neighbour | Move `monthToDateRange` out of `ExpenseList.jsx` so both screens share it; add `previousMonth(monthStr)` |
| `components/reporting/ProfitLossStatement.jsx` (new) | The statement itself (4.2) |
| `components/reporting/ProfitLossSummaryCards.jsx` (new) | Four stat cards: Revenue, Gross profit, Expenses, Net profit |
| `containers/ReportsContainer.jsx` + `pages/ReportsPage.jsx` (new) | Route `/reports`: holds the month state (URL search param `?month=2026-10`), Suspense/error boundary |
| `App.jsx` | Add `/reports` inside the `ProtectedRoute` group |
| `utils/constants.js` | Add a "Reports" entry to `NAV_LINKS` (it must appear in both `Sidebar` and `BottomNav`; check the mobile bottom bar fits) |
| `containers/DashboardContainer.jsx` | Optional: a compact "This month" net profit card linking to `/reports` |

### 4.2 The statement layout

Month picker at the top (`<input type="month">` reusing the pattern from `ExpenseList.jsx`, default = current month, with previous/next month buttons), a "Compare with previous month" toggle, then:

```
                                  October 2026      September 2026     Change
Sales revenue                       ₨ 1,250,000        ₨ 1,100,000      +13.6%
Cost of goods sold (landed cost)   −₨   900,000       −₨   820,000
                                    ─────────────
Gross profit                        ₨   350,000        ₨   280,000      +25.0%
  Gross margin                          28.0 %             25.5 %
Stock losses (damaged / adjust.)   −₨    12,000       −₨     8,000
Expenses
   Rent                            −₨    60,000       ...
   Salaries                        −₨    80,000       ...
   Food / daily                    −₨    21,000       ...
                                    ─────────────
Net profit                          ₨   177,000        ₨   140,000      +26.4%

Not included:  Draft expenses ₨ 15,000 · Sales without item/cost data ₨ 40,000
```

- Show `warnings` from the API as a visible notice, not hidden in a tooltip.
- Negative net profit uses the destructive colour, as `SalesOrderDetail`'s margin badge already does.
- Money through `CurrencyAmount` / `formatPKR`. Never `Number()` arithmetic on money in the component; all math is server-side. (The percentage change column is a display-only ratio and is the one allowed exception; compute it from the two Decimal strings with care, and show "—" when the previous value is 0.)
- Expense rows link to `/expenses` with the category and month pre-filtered (URL params).
- **Responsive (CLAUDE.md 3.7):** below `sm` render as stacked cards, one per section, with the comparison as a second line; the table version sits in `overflow-x-auto` only for `sm` and up. Verify at 375, 768 and 1280 px.
- **Print / export:** a "Print" button using a print stylesheet (hide nav, keep the statement) as v1. CSV or PDF export is a later step; `StockListShare.jsx` is the precedent for generating shareable output if an image is wanted for WhatsApp.

### 4.3 Small related fixes (same feature, low risk)

1. `ExpenseList.jsx` summary text says "spent matching the filters" and sums drafts. Either default the list's status filter to `confirmed`, or label the total "including drafts". Otherwise the Expenses screen total will not match the P&L expense total.
2. `Margin by Item` (`MarginReportTable.jsx`) is rolling-window only. Add a note under its title ("rolling window, not a calendar month — use Reports for monthly profit") so the two screens are not confused. A later step can give it the same date-range inputs.
3. `ProtectedRoute` ignores `state.from` after login (post-login always goes to `/settings`). Not part of this feature; noted because deep links to `/reports?month=...` will land on Settings after a re-login.

### 4.4 Frontend verification

- Pick a month with known data; compare every number with the sum of the sales order detail screens (revenue, cost, margin) and the Expenses screen filtered to that month and `confirmed`.
- Empty month shows zeros and no errors; a month before any data likewise.
- Previous month across a year boundary (January → December of the prior year).
- Toggle compare on and off without a full reload (query key includes the flag).
- Loading and error states render inside the container's Suspense/error boundary.

---

## 5. Phase 2 (separate follow-up): balance statement "as of" a date

Today's statement cannot show the position at the end of last month. This is harder than the P&L because three of its four numbers are historical reconstructions:

| Component | How to get it as of date D |
|---|---|
| Cash by account | `sum(debit − credit)` from `ledger_entry` where `payment_account_id` is set and `entry_date <= D`. Works, **but** payment-account opening balances are dated the day they were entered (1.3 point 7), so they would be excluded for any D before that day |
| Receivables / payables by party | Same ledger filter with `entry_date <= D`. Same opening-balance dating problem for parties |
| Inventory value | Not in the ledger. Reconstruct each lot's remaining quantity at D from `qty_received` minus the sum of `stock_movement.qty_delta` with `movement_date > D`, times `landed_cost_pkr`. `receipt` movements have `qty_delta = qty_received` (`inventory/service.py`), so lots received after D must be excluded by `received_date <= D` |
| Net position | cash + receivable − payable + inventory |

**Prerequisite:** give opening-balance ledger entries a business date (a `opening_date` on the create payload, defaulting to today), otherwise an as-of balance statement for past dates is wrong. Add `as_of: date | None = None` to `GET /reporting/balance-statement` (default today, so the existing frontend keeps working) and an as-of date picker to `BalanceStatement.jsx`. Do not start this until the P&L ships and the opening-balance dating question is decided.

---

## 6. Optional later: make the ledger a real P&L ledger

Only if you want the ledger itself to answer "revenue / COGS / expenses". This is a larger accounting change, not needed for the report above.

- On sale: credit a "Sales Revenue" entry, debit "Cost of Goods Sold" and credit "Inventory" at the FIFO cost.
- On expense: post to an "Expense — <category>" account.
- On damage/adjustment: post a "Stock Loss" entry.
- On cargo: record what is owed to the cargo agent.
- Backfill every historical sale, expense and movement in a migration.
- Because `CLAUDE.md` makes the ledger append-only and `update_expense` currently edits ledger rows in place (`expenses/service.py::update_expense`), reversal entries would be needed.

Recommendation: do not do this now. The P&L in sections 3–4 reconciles with the existing screens and carries no migration risk.

---

## 7. Risks and open questions

| # | Question / risk | Impact | Resolve by |
|---|---|---|---|
| 1 | What do `SalesLogException` rows really represent, and is `amount_pkr` signed? (2.4) | Could understate revenue or double count stock losses | Query real data before building |
| 2 | Do any sales have an `order_date` in the future, or backdated across a month already "closed" in the owner's mind? | Month totals change after being read | Decide: allow, and accept that past months can change |
| 3 | Do any `sales_order_line` rows lack `sales_order_line_lot` rows (old imports)? | COGS understated, margin overstated | Warning in 3.3 step 7; run a one-off count query first |
| 4 | Which expenses are really inventory/stock purchases (e.g. local vendor purchases entered as expenses)? | Double counting with COGS | Check expense categories against local purchase orders; the day-book import project may have put local purchases in either place |
| 5 | Should vendor payments for stock appear anywhere on the P&L? | No — assets, not expenses. Confirm with the owner so the statement is not misread as "cash profit" | Add a one-line explanation in the UI |
| 6 | Server timezone for "today" | Off-by-one at month edges for existing endpoints | Check deployment timezone |
| 7 | Staff vs owner visibility of profit | Profit and margin are sensitive once multi-user exists (see `MULTI_USER_ANALYSIS.md` 5.3) | Gate `/reports` and `/reporting/profit-loss` with `require_admin` when roles exist |

---

## 8. Implementation order

1. **Data checks (read-only):** run the queries in section 7 rows 1, 3 and 4 against the real database and record the numbers.
2. **Backend:** schemas, shared revenue/COGS helper, `get_profit_loss`, router, exception. Check by hand with the API docs against a month you can total by hand.
3. **Backend tests** if the team wants them (3.6).
4. **Frontend plumbing:** service, query key, hook, shared date util.
5. **Frontend screen:** statement component, summary cards, `/reports` route, nav entry, print stylesheet, responsive pass at 375 / 768 / 1280.
6. **Small related fixes** (4.3).
7. **Reconcile with real data:** choose two real months; compare the report with the sales order screens and the Expenses screen; fix any difference before telling the owner it is correct.
8. **Later, separately:** as-of balance statement (section 5); ledger accounts (section 6) only if wanted.

## 9. Acceptance criteria

- [ ] `GET /reporting/profit-loss` returns correct revenue, COGS, gross profit, stock loss, expenses by category and net profit for any date range up to 366 days.
- [ ] For the same period, `gross_profit_pkr` equals the Margin by Item total.
- [ ] Only `confirmed` expenses count; draft expenses are reported separately and never in net profit.
- [ ] A line that drew stock from two lots is costed at both lot costs and revenue is not double counted.
- [ ] Unitemised sales and missing-cost lines produce visible warnings and are never silently included.
- [ ] All money is `Decimal`; no float arithmetic on currency anywhere.
- [ ] A user can pick a month, compare to the previous month, and print the statement on phone, tablet and desktop widths.
- [ ] No database writes, no migration (unless the optional index was needed).
- [ ] Reports access is restricted to admins once roles exist.
