# Phase 8 Backend Spec — Statement & Analytics

Governed by `PLAN.md` (what) and `CLAUDE.md` (how). This document is the missing middle layer: the exact schema, query design, and service logic needed to implement Phase 8 inside a new `backend/src/reporting/` package, consistent with what Phases 0–7 already built. Nothing here overrides `CLAUDE.md`'s conventions — every choice below either follows an existing precedent in the codebase (cited by file:line) or is flagged explicitly as a new decision this phase introduces. This domain does not exist yet at all — there is no `backend/src/reporting/` package, no migration (none needed — see §7), no route. Every citation below to `reporting/*` is proposed, not confirmed; citations to `ledger/`, `parties/`, `payments/`, `catalog/`, `inventory/`, `sales/` are all confirmed by reading the actual current code.

**Done when** (from `PLAN.md`): you can open one screen and know where the business stands, and one chart to know what to reorder from China next. **Build:** No new transactional tables — this phase reads what phases 1–7 already wrote. Balance statement: `LedgerEntry` grouped by account (cash/bank/mobile wallets, receivables and payables by party, inventory value from remaining `StockLot` quantity × cost). Fast/slow-mover chart: `SalesOrderLine` quantity by `Model` over a rolling window. Reorder priority: rank `Model`s by recent sell-through, write back to `Model.priority` from Phase 1 so it feeds the next purchase order. Margin report: sale rate vs landed cost per item. **Entities:** none new — read models over existing tables.

---

## 1. Where we stand

Confirmed by reading the actual code:

- **No `backend/src/reporting/` package exists.** `ls backend/src` lists `auth, cargo, catalog, config.py, crud.py, database.py, exceptions.py, expenses, inventory, ledger, main.py, middlewares, models.py, pagination.py, parties, payments, purchasing, sales, security.py` — no `reporting`. Grepping `reporting|statement|analytics|sell_through|reorder|margin` (case-insensitive) across all of `src` surfaces only `parties`'s existing `PartyStatementRead`/`get_party_statement` (Phase 4, a single-party drill-down, not an aggregate report) and `sales/schemas.py`'s per-line `margin_pkr`/`total_margin_pkr` computed fields (Phase 4, per-sale margin, not an aggregate report grouped by item). Nothing resembling a balance statement, sell-through ranking, or reorder-priority write-back exists anywhere. This phase is fully greenfield.
- **`ledger/models.py:10-27`**'s `LedgerEntry` has everything this phase's balance statement needs already: `entry_date`, `account` (free-text, not an FK — see below), `debit`/`credit` (`Numeric(12,2)`), `reference_type`/`reference_id` (loose, unvalidated pair), `party_id` (nullable FK), `payment_account_id` (nullable FK). **No change to `ledger/models.py` or `ledger/service.py` this phase.** `ledger/service.py` has exactly one function, `post_entry()` (`ledger/service.py:9-35`) — it only ever inserts, never aggregates; every "group by" query in the codebase today is hand-written inline in the *consuming* domain's `service.py`, not centralized in `ledger/`. This phase follows that same convention: its aggregation queries live in `reporting/service.py`, not in `ledger/`.
- **The account-leg / party-leg double-entry pattern is the load-bearing fact for the balance statement's per-party section.** `payments/service.py::create_payment_transaction` (`payments/service.py:148-193`) posts **two** `LedgerEntry` rows per transaction when a party is linked: an account leg (`payment_account_id` set, `party_id` left `None`) signed from the account's point of view, and a party leg (`party_id` set, `payment_account_id` left `None`) signed from the party's point of view — `credit` reduces a receivable on `direction="in"`, `debit` reduces a payable on `direction="out"` (`payments/service.py:175-185`). Because the two legs never share a row, `GROUP BY payment_account_id` and `GROUP BY party_id` over the same `ledger_entry` table never double-count each other — each grouping only ever sees the rows meant for it (rows for the other grouping have that column `NULL`).
- **`payments/service.py::get_account_balances`** (`payments/service.py:116-145`) is the **correct reference pattern** to copy for any "group `LedgerEntry` by an FK, sum `debit - credit`, done" query: `SELECT payment_account_id, SUM(debit - credit) FROM ledger_entry WHERE payment_account_id IS NOT NULL GROUP BY payment_account_id`, then map each active `PaymentAccount` to its sum (defaulting to `0` if absent). Its inline comment explains *why* it does **not** add `PaymentAccount.opening_balance` on top of the ledger sum: the opening balance is itself posted as a `LedgerEntry` row at account-creation time (`payments/service.py:79`, `reference_type="payment_account_opening_balance"`), so it's already inside the sum — adding the column again would double it.
- **`parties/service.py::get_party_statement`** (`parties/service.py:118-148`) does exactly that double-count, and the bug is self-acknowledged in the *other* file's comment (`payments/service.py:132-137`): it seeds `running = party.opening_balance` **and then** iterates every `LedgerEntry` row for that party — which includes the very row that posted the opening balance in the first place (`parties/service.py:71-86`, `create_party`, posts `account="Party Opening Balance"` whenever `payload.opening_balance != 0`, using the sign convention `opening_balance > 0 → debit`, `opening_balance < 0 → credit` — i.e. **positive = receivable, negative = payable**, the same convention `Accounts Receivable`/`Accounts Payable` entries already use). **This phase's balance statement must follow `get_account_balances`'s shape for the party section (§2.2), not `get_party_statement`'s** — copying the latter would silently import a known bug into the one report this whole system was built around (`PLAN.md` Principle 4: "That's what makes the balance statement in Phase 8 *trustworthy* instead of a recomputed guess").
- **Every `LedgerEntry.account` string value written by the codebase today**, grepped across every domain's `service.py`:

  | Value | Posted by |
  |---|---|
  | `"Accounts Payable"` | `purchasing.service.create_purchase_order` (credit); `payments.service.create_payment_transaction` (party leg, `direction="out"`) |
  | `"Accounts Receivable"` | `sales.service.create_sales_order` (debit); `payments.service.create_payment_transaction` (party leg, `direction="in"`) |
  | `"Inventory"` | `inventory.service.receive_purchase_order_line` (debit = `qty_received * landed_cost_pkr`, no `party_id`/`payment_account_id`) |
  | `"Payment Account Opening Balance"` | `payments.service.create_payment_account` |
  | `"Party Opening Balance"` | `parties.service.create_party` |
  | `PaymentAccount.label` (e.g. `"Meezan Bank"`, `"Cash drawer"`) | `payments.service.create_payment_transaction` (account leg) |

  `account` is a bare `str` column, not an FK into any lookup table, and it is a **point-in-time copy** of `PaymentAccount.label` for the account leg — if a label is renamed later via the generic CRUD's `PUT`, historical `LedgerEntry.account` strings do not follow it. **Grouping must use the FK columns (`payment_account_id`, `party_id`), never the `account` string** — the string is display history, not a stable join key. The `"Inventory"` entries have neither FK set and exist purely as an audit trail of receipts; this phase's inventory-value figure is **not** computed from them (see §2.2 — it reads `StockLot` directly, per `PLAN.md`'s own wording).
- **`catalog/models.py:15-21`**: `Model.priority: Mapped[int] = mapped_column(default=0)` already exists, exactly as `PLAN.md` Phase 1 promised ("a `priority` field left for Phase 8"). Confirmed by grep (`priority` appears only in `catalog/models.py` and `catalog/schemas.py` — `ModelRead.priority: int`, `ModelUpdate.priority: int | None = None`) that **nothing reads or writes this column anywhere today** — it is a pure placeholder. This phase is its first real consumer, and since nothing exists yet, **this phase must define the ranking scale itself** (§2.3) — there is no existing convention to match.
- **`inventory/models.py:10-22`**: `StockLot.qty_remaining` and `.landed_cost_pkr` are both `Numeric`. `StockLot` has **no `is_active` column** (a depleted lot, `qty_remaining == 0`, is simply spent, not soft-deleted). `inventory.service.list_stock_lots` (`inventory/service.py:176-196`) already filters `StockLot.qty_remaining > 0` when `include_depleted=False` — the exact filter this phase's inventory-value sum needs.
- **`sales/models.py:26-42`**: `SalesOrderLine` stores only `qty` and `rate_pkr` — no landed-cost/margin column on the line itself. Cost is snapshotted one level down, in `SalesOrderLineLot` (`unit_cost_pkr`, a copy of the consumed `StockLot.landed_cost_pkr` at the moment of sale), one row per lot a FIFO consumption drew from. `sales/schemas.py:39-52`'s `SalesOrderLineRead` already computes `amount_pkr = qty * rate_pkr`, `cost_pkr = Σ(qty_consumed * unit_cost_pkr)`, `margin_pkr = amount_pkr - cost_pkr` as Pydantic `@computed_field`s — this phase's margin report replicates the same three formulas as SQL aggregates grouped by `item_id`, rather than reusing the Pydantic properties (those only run per already-loaded ORM object; a report needs a `GROUP BY` over the whole table). Both `SalesOrder.lines` and `SalesOrderLine.consumptions` are `lazy="raise"` — irrelevant here since this phase never loads `SalesOrder`/`SalesOrderLine` ORM objects with their relationships, only runs aggregate `select()`s against the tables directly.
- **`money()` is duplicated per domain, not shared.** `cargo/utils.py`, `sales/utils.py`, `purchasing/utils.py`, `inventory/utils.py`, `payments/utils.py` each define an identical `money(value: Decimal) -> Decimal` (quantize to `Decimal("0.01")`, `ROUND_HALF_UP` — matches Postgres `NUMERIC(x,2)` rounding, unlike `Decimal`'s default `ROUND_HALF_EVEN`). This phase adds its own `reporting/utils.py` copy rather than importing another domain's (§3.3) — consistent with the established (if repetitive) house style, and it's also used to round the quantity sums this phase computes (`StockLot.qty_remaining`/`SalesOrderLine.qty` are also `Numeric(x,2)`, same scale as money).
- **No `outerjoin` with a conditional `ON` clause (`and_(...)` inside a join) exists anywhere in the codebase yet** — `inventory/service.py:78` has the only existing `outerjoin`, and its `ON` is a plain equality. This phase's sell-through/margin queries need multi-table joins filtered by a date window; §2.4 flags a real correctness pitfall this shape can hit and the subquery-based fix this spec adopts instead.
- **`main.py:1-34`**: every domain adds one import line and one `app.include_router(..., prefix="/<domain>")` line. Domains with a single hand-written router and no sub-resource split (`parties/router.py:15`, `payments/router.py`'s hand-written pieces) declare `router = APIRouter(tags=["<domain>"])` with **no prefix of its own**, letting `main.py`'s `prefix="/<domain>"` be the only prefix. Domains whose hand-written router represents one named sub-resource (e.g. `sales/router.py:15` → `APIRouter(prefix="/sales-orders", tags=["sales"])`, deliberately combined with `main.py`'s `prefix="/sales"` into `/sales/sales-orders/...`) are the exception, used when the domain's main noun differs from the domain name. Reporting has four distinct, equally-weighted report endpoints, not one named sub-resource — it follows the `parties`/no-extra-prefix shape (§6).
- **Auth dependency shape**: every route, generic or hand-written, takes `_current_user: Annotated[User, Depends(get_current_user)]` (e.g. `sales/router.py:22`); there are no unauthenticated data routes anywhere to except this phase from.
- **Migration head**: `backend/migrations/versions/2026-08-10_add_expenses.py:15` — `revision = 'aa6c8f189438'`, the current head. This phase adds no columns and no tables, so **no new Alembic revision is needed at all** (§7) — the first phase where that's true.

---

## 2. Design decisions

### 2.1 One new package, `reporting/`, with no `models.py` — every query reads across other domains' tables directly

Unlike every prior phase, `reporting/` owns no SQLAlchemy models. `CLAUDE.md` §2.1 already anticipated this exact shape for `reporting/` on the frontend side ("Phase 8 — reads other domains' data, owns none"); the backend package mirrors it. Concretely this phase adds: `reporting/schemas.py`, `reporting/constants.py`, `reporting/utils.py`, `reporting/service.py`, `reporting/router.py`. **No `reporting/models.py`, no migration.** No `reporting/dependencies.py` either — every endpoint is a plain aggregate query driven by query parameters (a `window_days` int), never a path parameter naming one specific row, so there is no "resolve this id or 404" dependency to write (contrast with every prior domain's `valid_<entity>` dependency).

This makes `reporting/` a *third* effectively one-way domain, alongside `ledger/` and `parties/` (`CLAUDE.md` §2.1's explicit two): everything else can be imported *into* `reporting/`, but nothing should ever import `reporting/` back — a domain reporting on the whole system is, by construction, downstream of everything. `CLAUDE.md` doesn't list this as a formal rule the way it does for `ledger/`/`parties/`, but it falls out of the same reasoning and is worth stating explicitly here since it's new.

**No `reporting/exceptions.py` either.** Every endpoint's only input is a bounded `window_days` integer, validated at the `Query(ge=..., le=...)` layer (§6) — there is no "not found" case (an empty report is a valid, zero-length answer, not an error) and no business-rule violation possible from a read-only aggregate. If a future addition needs one, it follows `src/exceptions.py`'s existing `AppException`/`NotFoundException`/`ConflictException` base classes, translated by the same global `@app.exception_handler(AppException)` in `main.py:20-22` every other domain already relies on.

### 2.2 Balance statement: three independently-computed sections, each following `get_account_balances`'s shape — never `get_party_statement`'s

Per `PLAN.md`, the balance statement has three parts: cash/bank/mobile wallets, receivables/payables by party, inventory value. Each is its own independent query; there is no single "the balance statement" SQL statement, because the three live on different FK columns and one of them (inventory) isn't in the ledger at all:

1. **Cash/bank/wallets** — this phase does not reimplement this at all. It calls `payments.service.get_account_balances(db)` directly (§1) and reuses its `PaymentAccountBalanceRead` list verbatim as the `cash_accounts` field. Zero new query — the existing function already does exactly this, correctly.
2. **Receivables/payables by party** — a *new* query, but the same shape as `get_account_balances`, substituting `party_id` for `payment_account_id`:
   ```sql
   SELECT party.id, party.name, party.roles, SUM(debit - credit)
   FROM party JOIN ledger_entry ON ledger_entry.party_id = party.id
   GROUP BY party.id, party.name, party.roles
   HAVING SUM(debit - credit) != 0
   ```
   Positive sum = receivable (they owe us), negative = payable (we owe them) — the same sign convention `create_party`'s opening-balance posting already established (§1). The `INNER JOIN` (not `LEFT JOIN`) naturally drops any party with zero ledger activity — and since `create_party` only posts an opening-balance row `if payload.opening_balance != 0` (§1), a party with a zero opening balance and no transactions never had a row to begin with, so this isn't a filtering choice so much as the query correctly reporting "nothing to report." The added `HAVING` clause additionally drops parties whose net balance has since settled back to exactly zero (fully paid) — a deliberate choice: "receivables and payables by party" (`PLAN.md`'s own words) reads as "who currently owes what," not a list of every party that ever transacted.
   
   **Deliberately no `WHERE party.is_active` filter.** `payments.get_account_balances` *does* filter `PaymentAccount.is_active.is_(True)` (§1) — this phase's party query does not, on purpose, and the asymmetry is worth calling out rather than silently copying: a deactivated `Party` can still carry an outstanding balance, and `CLAUDE.md` §4's "history must never break" / soft-delete rule exists precisely so an old vendor or customer's unresolved balance is never allowed to vanish from a statement that exists to answer "where does the business stand." A cash *account* being deactivated is closer to "we stopped using this bank account," where excluding it from the balances list going forward is reasonable; a *party* being deactivated is closer to "we stopped actively dealing with this contact," which says nothing about whether they still owe money.
3. **Inventory value** — per `PLAN.md`'s explicit wording ("inventory value from remaining `StockLot` quantity × cost"), this reads `StockLot` directly, **not** the ledger's `"Inventory"` entries (§1 already establishes those entries have no FK to aggregate by and exist only as a receipt audit trail):
   ```sql
   SELECT SUM(qty_remaining * landed_cost_pkr) FROM stock_lot WHERE qty_remaining > 0
   ```
   Same filter `inventory.service.list_stock_lots` already uses for `include_depleted=False` (§1).

The three sections' totals are then combined into one `net_position_pkr = total_cash_pkr + total_receivable_pkr - total_payable_pkr + inventory_value_pkr` — a genuinely new figure (nothing in phases 0–7 computes anything like it), included because "know where the business stands" (`PLAN.md`'s own done-when line) reads as wanting one bottom-line number, not just three disconnected sections a user has to add up by hand.

### 2.3 Reorder priority's ranking scale: `priority = 1` means "sell this fastest, reorder it first"

`Model.priority` (§1) has never been given a defined scale — this phase has to invent one, since nothing else in the codebase constrains it. Two shapes were possible: (a) store the raw quantity sold as `priority` (a bigger number = more urgent), or (b) store the *rank position* (`1` = top seller). This spec picks (b) because:
- It's directly usable for sorting a `ReorderPriorityTable` (`CLAUDE.md` §3.3) with no further transformation — `ORDER BY priority ASC` is "what to reorder first," in plain reading order.
- It's stable in scale regardless of how many units actually sold in a given window — a slow month with every model selling single digits still produces a clean `1..N` ranking, where a raw-quantity scale would compress toward zero and lose ranking resolution.
- It matches the field's own name — "priority 1" reading as "highest priority" is the ordinary meaning of the word, whereas "priority = 340 units" is not obviously a priority at all without a legend.

Rank is assigned by `ORDER BY qty_sold DESC, model.id ASC` — ties (including "zero sold, tied with every other zero-sold model") broken deterministically by id, so the same underlying sales data always reproduces the exact same ranking, not just the same ordering. Only `Model.is_active.is_(True)` rows are ranked (§2.4) — a discontinued model has no business being told to "reorder first."

### 2.4 The rolling window is computed with pre-aggregating subqueries, not an outer join with a date condition inside the `ON` clause — a correctness pitfall worth naming explicitly

A first-draft version of the sell-through query looks tempting: chain `Model → Item → SalesOrderLine → SalesOrder` with plain `outerjoin`s (so a model with zero sales still appears, coalesced to `0`), and push the date-window filter into the *last* join's `ON` clause instead of a `WHERE` (since a `WHERE` there would silently turn the whole chain back into an inner join, dropping zero-sale models — the opposite of what a `LEFT JOIN` is for). **This is wrong**, and subtly so: even when the final `SalesOrder` join fails to match because the date is out of range, the earlier `SalesOrderLine` row is still present in the joined result (it matched on `item_id` in its own, earlier join) — so `SUM(SalesOrderLine.qty)` still counts out-of-window sales, silently. No existing query in this codebase has this shape (§1), so there's no precedent to blindly copy, and it's exactly the kind of bug that would pass a manual smoke test (numbers look plausible) while quietly including old sales in a "last 30 days" chart.

This spec avoids it entirely by pre-aggregating in a subquery *before* joining to `Model`, the same shape `sales.schemas`'s margin math already suggests and this phase's own margin-report query needs anyway (§5.4):

```sql
-- qty actually sold per item, only counting sales inside the window (INNER join — correct here,
-- because this subquery's whole job is "sales in this window", nothing else)
qty_by_item AS (
  SELECT sales_order_line.item_id, SUM(sales_order_line.qty) AS qty_sold
  FROM sales_order_line JOIN sales_order ON sales_order.id = sales_order_line.sales_order_id
  WHERE sales_order.order_date BETWEEN :start_date AND :end_date
  GROUP BY sales_order_line.item_id
),
-- rolled up to model level
qty_by_model AS (
  SELECT item.model_id, SUM(qty_by_item.qty_sold) AS qty_sold
  FROM item JOIN qty_by_item ON qty_by_item.item_id = item.id
  GROUP BY item.model_id
)
-- NOW left-join onto every active model, so zero-sale models still appear at qty_sold = 0
SELECT model.*, COALESCE(qty_by_model.qty_sold, 0)
FROM model LEFT JOIN qty_by_model ON qty_by_model.model_id = model.id
WHERE model.is_active
ORDER BY COALESCE(qty_by_model.qty_sold, 0) DESC, model.id ASC
```

The `LEFT JOIN` that needs to preserve zero-sale rows happens *last*, against an already-correct, already-window-filtered aggregate — so there's no join whose `ON`-clause date filter could be silently bypassed. This is the shape §5.2/§5.4's actual service code uses.

### 2.5 Reorder priority is exposed as a `GET`, and it writes to `Model.priority` as a side effect of that read — not a separate `POST` action

`CLAUDE.md` §3.2's frontend tree spells out `reportingHooks/ (reportingQueries.js — read-only, this domain has no mutations)` — a direct, explicit statement that the reporting domain's frontend hooks layer has no `*Mutations.js` file at all. But `PLAN.md`'s Phase 8 line is equally explicit the other way: "rank Models by recent sell-through, **write back to `Model.priority`**." Something in this system has to persist that write, and per `CLAUDE.md`'s own frontend contract, it cannot be a dedicated mutation hook in `reportingHooks/`.

This spec resolves the tension by making `GET /reporting/reorder-priority` **compute the ranking and persist it to `Model.priority` in the same request**, then return the resulting ranked list — a "read with a side effect," not a `POST`. This keeps the eventual frontend hook a plain `useQuery` (satisfying `CLAUDE.md`'s "no mutations" line for this domain, since from the frontend's point of view it only ever calls a query, never a mutation), and the write is genuinely idempotent at the data level: calling it twice in a row against unchanged sales data reproduces the identical ranking both times (§2.3's tie-break rule guarantees the ordering is deterministic, not just the set of qty values). `GET /reporting/sell-through` is a separate, side-effect-free endpoint returning the *same* ranking shape for the chart (`SellThroughChart`, `CLAUDE.md` §3.3) — it never touches `Model.priority`, so opening the dashboard's chart alone never mutates anything.

This is a real, deliberate deviation from ordinary HTTP semantics (a `GET` is conventionally expected to be safe/cacheable), flagged here rather than silently done, with the tradeoff spelled out in §9 for whoever writes the frontend hook: if `reportingHooks/reportingQueries.js` wires this endpoint's `useQuery` with default TanStack Query settings, a background refetch on window focus would silently re-rank `Model.priority` every time the tab regains focus. That's arguably *fine* (the ranking is supposed to always reflect current data — this isn't corrupting anything), but it's a behavior the frontend spec should call out explicitly rather than an accidental side effect of default caching settings, so this backend spec is naming it now rather than leaving it to be discovered later.

### 2.6 Margin report is item-level, matching `PLAN.md`'s literal wording, not pre-rolled-up to `Model`

`PLAN.md`: "Margin report: sale rate vs landed cost per **item**." This spec returns one row per `Item` (not per `Model`), each carrying its `model_id`/`model_name` alongside so the frontend can group/filter by model itself if it wants a rolled-up view — matching the same "reporting owns none, reads other domains' data" posture (§2.1): the backend doesn't decide the frontend's preferred grouping, it returns the finest-grained truth (`CLAUDE.md`'s `MarginReport`/margin-by-item screen isn't named in `CLAUDE.md` §3.3's list of reporting components — only `BalanceStatement`, `SellThroughChart`, `ReorderPriorityTable` are — so this endpoint's exact frontend consumer is left to the Phase 8 frontend spec; this backend spec exists so that whichever shape it picks has real data to call).

---

## 3. New: `backend/src/reporting/`

### 3.1 `reporting/constants.py`

```python
DEFAULT_WINDOW_DAYS = 30
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 730  # ~2 years — generous, but still a bound, so an unbounded window can't force a full-table scan
```
Shared by every windowed report (`sell-through`, `reorder-priority`, `margin`) — the balance statement takes no window at all (§2.2 — it's a point-in-time snapshot over everything ever posted, there is nothing to bound).

### 3.2 `reporting/schemas.py`

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from src.payments.schemas import PaymentAccountBalanceRead


class PartyBalanceRead(BaseModel):
    party_id: int
    name: str
    roles: list[str]
    balance_pkr: Decimal  # positive = receivable (they owe us), negative = payable (we owe them) — §2.2


class BalanceStatementRead(BaseModel):
    as_of: date
    cash_accounts: list[PaymentAccountBalanceRead]
    total_cash_pkr: Decimal
    party_balances: list[PartyBalanceRead]
    total_receivable_pkr: Decimal
    total_payable_pkr: Decimal
    inventory_value_pkr: Decimal
    net_position_pkr: Decimal


class SellThroughEntryRead(BaseModel):
    model_id: int
    model_name: str
    qty_sold: Decimal
    rank: int  # 1 = fastest mover in this window


class SellThroughRead(BaseModel):
    window_days: int
    start_date: date
    end_date: date
    entries: list[SellThroughEntryRead]


class ReorderPriorityEntryRead(BaseModel):
    model_id: int
    model_name: str
    qty_sold: Decimal
    priority: int  # the value just written to Model.priority — 1 = reorder first, §2.3


class ReorderPriorityRead(BaseModel):
    window_days: int
    start_date: date
    end_date: date
    entries: list[ReorderPriorityEntryRead]


class MarginReportEntryRead(BaseModel):
    item_id: int
    sku: str
    model_id: int
    model_name: str
    qty_sold: Decimal
    revenue_pkr: Decimal
    cost_pkr: Decimal
    margin_pkr: Decimal
    margin_pct: float  # a ratio, not currency — CLAUDE.md §2.4's Decimal rule governs money fields, not this one


class MarginReportRead(BaseModel):
    window_days: int
    start_date: date
    end_date: date
    entries: list[MarginReportEntryRead]
    total_revenue_pkr: Decimal
    total_cost_pkr: Decimal
    total_margin_pkr: Decimal
```
`BalanceStatementRead` directly reuses `payments.schemas.PaymentAccountBalanceRead` for `cash_accounts` (§2.2, decision 1) rather than redefining an identical shape — the only cross-domain schema reuse in this phase, justified because it's the *exact same data*, not a coincidentally-similar shape. No `PaginatedResponse` anywhere in this file (§1's `pagination.py` note) — every report here is one bounded aggregate payload (at most one row per `Model`/`Item`/`PaymentAccount`/`Party` with nonzero activity), never a page-able list.

### 3.3 `reporting/utils.py`

```python
from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round to 2dp half-up — matches Postgres NUMERIC(x,2) rounding, unlike Decimal's default (half-even).
    Also used to round quantity sums in this module: StockLot.qty_remaining and SalesOrderLine.qty are
    both NUMERIC(10,2) — the same scale as the money columns this helper was written for."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
```
A deliberate copy of `sales/utils.py`'s (etc.) identical function (§1) — matches the established per-domain-duplication convention rather than introducing the first cross-domain util import in the codebase.

### 3.4 No changes to any existing file

`ledger/*`, `payments/*`, `parties/*`, `catalog/*`, `inventory/*`, `sales/*`, `crud.py`, `pagination.py`, `exceptions.py`, `models.py` — all unchanged (§1, §2.1). This phase is purely additive and read-only against every existing table except one column: `Model.priority`, updated in place by `reorder-priority` (§2.5) using the existing column, no schema change.

---

## 4. Service logic — `reporting/service.py`

### 4.1 Imports

```python
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models import Item, Model
from src.inventory.models import StockLot
from src.ledger.models import LedgerEntry
from src.parties.models import Party
from src.payments import service as payments_service
from src.reporting.schemas import (
    BalanceStatementRead,
    MarginReportEntryRead,
    MarginReportRead,
    PartyBalanceRead,
    ReorderPriorityEntryRead,
    ReorderPriorityRead,
    SellThroughEntryRead,
    SellThroughRead,
)
from src.reporting.utils import money
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot
```
No `and_`/`case` import — the pitfall in §2.4 is exactly what pre-aggregating subqueries let this module avoid needing either.

### 4.2 `get_balance_statement` (§2.2)

```python
async def get_balance_statement(db: AsyncSession) -> BalanceStatementRead:
    cash_accounts = await payments_service.get_account_balances(db)
    total_cash_pkr = money(sum((a.balance for a in cash_accounts), Decimal(0)))

    party_rows = (
        await db.execute(
            select(Party.id, Party.name, Party.roles, func.sum(LedgerEntry.debit - LedgerEntry.credit))
            .join(LedgerEntry, LedgerEntry.party_id == Party.id)
            .group_by(Party.id, Party.name, Party.roles)
            .having(func.sum(LedgerEntry.debit - LedgerEntry.credit) != 0)
        )
    ).all()
    party_balances = [
        PartyBalanceRead(party_id=pid, name=name, roles=roles, balance_pkr=money(balance))
        for pid, name, roles, balance in party_rows
    ]
    total_receivable_pkr = money(sum((p.balance_pkr for p in party_balances if p.balance_pkr > 0), Decimal(0)))
    total_payable_pkr = money(sum((-p.balance_pkr for p in party_balances if p.balance_pkr < 0), Decimal(0)))

    inventory_value_pkr = money(
        (
            await db.scalar(
                select(func.sum(StockLot.qty_remaining * StockLot.landed_cost_pkr)).where(
                    StockLot.qty_remaining > 0
                )
            )
        )
        or Decimal(0)
    )

    net_position_pkr = money(total_cash_pkr + total_receivable_pkr - total_payable_pkr + inventory_value_pkr)

    return BalanceStatementRead(
        as_of=date.today(),
        cash_accounts=cash_accounts,
        total_cash_pkr=total_cash_pkr,
        party_balances=party_balances,
        total_receivable_pkr=total_receivable_pkr,
        total_payable_pkr=total_payable_pkr,
        inventory_value_pkr=inventory_value_pkr,
        net_position_pkr=net_position_pkr,
    )
```
No `try/except IntegrityError`/`commit` anywhere — this function never writes, so it never needs the commit/rollback ceremony every write-path service function in this codebase has.

### 4.3 `_rank_models_by_sell_through` — shared by both windowed model reports (§2.3, §2.4)

```python
async def _rank_models_by_sell_through(
    db: AsyncSession, window_days: int
) -> tuple[date, date, list[tuple[Model, Decimal, int]]]:
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)

    qty_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLine.qty).label("qty_sold"),
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date)
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )
    qty_by_model = (
        select(
            Item.model_id.label("model_id"),
            func.sum(qty_by_item.c.qty_sold).label("qty_sold"),
        )
        .select_from(Item)
        .join(qty_by_item, qty_by_item.c.item_id == Item.id)
        .group_by(Item.model_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(Model, func.coalesce(qty_by_model.c.qty_sold, Decimal(0)))
            .select_from(Model)
            .outerjoin(qty_by_model, qty_by_model.c.model_id == Model.id)
            .where(Model.is_active.is_(True))
            .order_by(func.coalesce(qty_by_model.c.qty_sold, Decimal(0)).desc(), Model.id)
        )
    ).all()
    return start_date, end_date, [(model, money(qty), rank) for rank, (model, qty) in enumerate(rows, start=1)]
```
`select(Model, ...)` alongside `GROUP BY model.id` (implicit — there's no explicit `.group_by(Model.id)` needed here because this is the *outer* query and `qty_by_model`/`qty_by_item` already did the grouping; this final query is a plain join with no aggregate of its own beyond the already-aggregated subquery columns) — confirmed correct because `func.coalesce(qty_by_model.c.qty_sold, ...)` is not itself re-aggregated here, just carried through per row.

### 4.4 `get_sell_through` and `recalculate_reorder_priority` — same computation, only the latter writes (§2.5)

```python
async def get_sell_through(db: AsyncSession, window_days: int) -> SellThroughRead:
    start_date, end_date, ranked = await _rank_models_by_sell_through(db, window_days)
    return SellThroughRead(
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        entries=[
            SellThroughEntryRead(model_id=m.id, model_name=m.name, qty_sold=qty, rank=rank)
            for m, qty, rank in ranked
        ],
    )


async def recalculate_reorder_priority(db: AsyncSession, window_days: int) -> ReorderPriorityRead:
    start_date, end_date, ranked = await _rank_models_by_sell_through(db, window_days)
    for model, _qty, rank in ranked:
        model.priority = rank
    await db.commit()
    return ReorderPriorityRead(
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        entries=[
            ReorderPriorityEntryRead(model_id=m.id, model_name=m.name, qty_sold=qty, priority=rank)
            for m, qty, rank in ranked
        ],
    )
```
`recalculate_reorder_priority` mutates the already-loaded `Model` ORM instances returned by `_rank_models_by_sell_through`'s own query (they're attached to `db`'s session already, since that query loaded them) — no second fetch-by-id round trip needed. No `try/except IntegrityError` around this `commit()`: a plain integer column update on an existing row has no unique/FK constraint to violate, unlike every prior phase's `commit()` calls that follow a fresh `INSERT`.

### 4.5 `get_margin_report` (§2.6)

```python
async def get_margin_report(db: AsyncSession, window_days: int) -> MarginReportRead:
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)

    revenue_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLine.qty).label("qty_sold"),
            func.sum(SalesOrderLine.qty * SalesOrderLine.rate_pkr).label("revenue_pkr"),
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date)
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )
    cost_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLineLot.qty_consumed * SalesOrderLineLot.unit_cost_pkr).label("cost_pkr"),
        )
        .select_from(SalesOrderLineLot)
        .join(SalesOrderLine, SalesOrderLine.id == SalesOrderLineLot.sales_order_line_id)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date)
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(
                Item.id,
                Item.sku,
                Model.id,
                Model.name,
                revenue_by_item.c.qty_sold,
                revenue_by_item.c.revenue_pkr,
                cost_by_item.c.cost_pkr,
            )
            .select_from(revenue_by_item)
            .join(Item, Item.id == revenue_by_item.c.item_id)
            .join(Model, Model.id == Item.model_id)
            .outerjoin(cost_by_item, cost_by_item.c.item_id == revenue_by_item.c.item_id)
            .order_by(revenue_by_item.c.revenue_pkr.desc())
        )
    ).all()

    entries = []
    for item_id, sku, model_id, model_name, qty_sold, revenue_pkr, cost_pkr in rows:
        cost_pkr = cost_pkr or Decimal(0)
        margin_pkr = money(revenue_pkr - cost_pkr)
        margin_pct = float(round((margin_pkr / revenue_pkr) * 100, 2)) if revenue_pkr else 0.0
        entries.append(
            MarginReportEntryRead(
                item_id=item_id,
                sku=sku,
                model_id=model_id,
                model_name=model_name,
                qty_sold=money(qty_sold),
                revenue_pkr=money(revenue_pkr),
                cost_pkr=money(cost_pkr),
                margin_pkr=margin_pkr,
                margin_pct=margin_pct,
            )
        )

    total_revenue_pkr = money(sum((e.revenue_pkr for e in entries), Decimal(0)))
    total_cost_pkr = money(sum((e.cost_pkr for e in entries), Decimal(0)))
    total_margin_pkr = money(total_revenue_pkr - total_cost_pkr)

    return MarginReportRead(
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        entries=entries,
        total_revenue_pkr=total_revenue_pkr,
        total_cost_pkr=total_cost_pkr,
        total_margin_pkr=total_margin_pkr,
    )
```
Driven `FROM revenue_by_item` (an inner-join-derived subquery, §2.6 — an item with zero sales in the window simply has no row here, correctly excluded, since "margin per item" is meaningless for an item that didn't sell) with `cost_by_item` **outer**-joined on top defensively: every `SalesOrderLine` is guaranteed at least one `SalesOrderLineLot` by the FIFO-consumption service logic in `sales/service.py` (a sale can't happen without consuming stock), so `cost_pkr` should never actually be `NULL` here — the `outerjoin` + `cost_pkr or Decimal(0)` fallback is belt-and-suspenders against that invariant, not an expected code path, kept because nothing in this new read-only module should be able to raise a `TypeError` from an unexpected `NULL` on a report a user is casually opening. `margin_pct` guards `revenue_pkr == 0` even though that can't happen given the `revenue_by_item`-driven `FROM` (revenue is always `qty * rate_pkr` with both `Field(gt=0)`-constrained at creation, `sales/schemas.py:12-13`) — same defensive posture.

---

## 5. API surface — `reporting/router.py`

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.reporting import service
from src.reporting.constants import DEFAULT_WINDOW_DAYS, MAX_WINDOW_DAYS, MIN_WINDOW_DAYS
from src.reporting.schemas import BalanceStatementRead, MarginReportRead, ReorderPriorityRead, SellThroughRead

router = APIRouter(tags=["reporting"])  # no own prefix — main.py's is the only one, matches parties/router.py (§1)

WindowDays = Annotated[int, Query(ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS)]


@router.get("/balance-statement", response_model=BalanceStatementRead)
async def balance_statement(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_balance_statement(db)


@router.get("/sell-through", response_model=SellThroughRead)
async def sell_through(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    window_days: WindowDays = DEFAULT_WINDOW_DAYS,
):
    return await service.get_sell_through(db, window_days)


@router.get("/reorder-priority", response_model=ReorderPriorityRead)
async def reorder_priority(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    window_days: WindowDays = DEFAULT_WINDOW_DAYS,
):
    return await service.recalculate_reorder_priority(db, window_days)


@router.get("/margin", response_model=MarginReportRead)
async def margin_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    window_days: WindowDays = DEFAULT_WINDOW_DAYS,
):
    return await service.get_margin_report(db, window_days)
```

| Method | Path | Notes |
|---|---|---|
| GET | `/reporting/balance-statement` | §4.2 — no query params, always "as of now" |
| GET | `/reporting/sell-through` | §4.4 — `?window_days=` (default 30), read-only |
| GET | `/reporting/reorder-priority` | §4.4 — `?window_days=` (default 30), **writes `Model.priority`** (§2.5) |
| GET | `/reporting/margin` | §4.5 — `?window_days=` (default 30), read-only |

`main.py` gets exactly one new import and one new `include_router` line, appended after `expenses` (the current last domain), matching every other phase:
```python
from src.reporting.router import router as reporting_router
...
app.include_router(reporting_router, prefix="/reporting")
```

No route-ordering trap exists here (`payments/router.py`'s literal-vs-`{account_id}` `/balances` issue, `phase-6-backend.md §6`) — every path in this router is a distinct literal segment (`/balance-statement`, `/sell-through`, `/reorder-priority`, `/margin`), no `{param}` route anywhere to collide with.

---

## 6. Migration

**None.** No new table, no new column, no new index — the only mutation this phase ever performs is an `UPDATE model SET priority = :rank WHERE id = :id` against a column that has existed since Phase 1's migration. Current head stays `aa6c8f189438` (`migrations/versions/2026-08-10_add_expenses.py:15`) — the first phase spec in this series where §7 (migration) is empty by design, not merely "small."

---

## 7. Manual testing (`backend/scripts/seed.py` unchanged — no seed additions needed or useful here)

There's nothing to seed specifically for Phase 8 — its endpoints only produce meaningful, non-empty output once real data exists across Phases 1–7 (a purchase order, a landed shipment, a receipt into stock, a sale). `scripts/seed.py` today seeds a user, an exchange rate, payment methods/accounts, cargo modes/cost bases, and one china vendor (`scripts/seed.py:27-97`) — enough to *start* the flow below, but every step still has to be driven through the app/API once to generate the transactional history these reports read.

1. Seed (`python -m scripts.seed ...`), then walk one full purchase → cargo → receive → sell cycle through the existing endpoints from Phases 1–4 (a `PurchaseOrder` with at least one line, a `CargoShipment` allocating cost to it, `POST /inventory/stock-lots/receive` turning the line into a `StockLot`, then a `SalesOrder` selling some of that stock to a `customer`-role `Party`).
2. `GET /reporting/balance-statement` → confirm `cash_accounts` matches `GET /payments/payment-accounts/balances` exactly (same numbers, same source function, §4.2), `party_balances` shows the customer with a positive `balance_pkr` (receivable) if unpaid, `inventory_value_pkr` reflects whatever `StockLot.qty_remaining` is left after the sale, and `net_position_pkr` is the arithmetic sum of the other totals.
3. Post a `PaymentTransaction` against that customer (`POST /payments/payment-transactions`, `direction="in"`) for less than the full amount owed → `GET /reporting/balance-statement` again, confirm the party's `balance_pkr` dropped by exactly the payment amount (not to zero, not double-counted) and `total_cash_pkr` rose by the same amount.
4. `GET /reporting/sell-through?window_days=30` → confirm the model just sold appears with `qty_sold` equal to the sales-order line's `qty` and `rank=1` (assuming it's the only model with any sales), every other active `Model` appears with `qty_sold=0` and later ranks.
5. `GET /catalog/models/{id}` (the model just sold) → confirm `priority` is still whatever it was before (unchanged — `sell-through` never writes).
6. `GET /reporting/reorder-priority?window_days=30` → confirm the same ranking as step 4, then re-fetch `GET /catalog/models/{id}` → confirm `priority` now equals the `rank` returned in step 6's response (the write-back, §2.5).
7. Call `GET /reporting/reorder-priority?window_days=30` a second time with no new sales in between → confirm the response is byte-for-byte identical to the first call (idempotence, §2.3/§2.5).
8. `GET /reporting/margin?window_days=30` → confirm the sold item's `revenue_pkr` equals `qty * rate_pkr` from the sales-order line, `cost_pkr` equals `qty_consumed * unit_cost_pkr` summed over that line's `SalesOrderLineLot` rows (visible via `GET /sales/sales-orders/{id}`'s existing `cost_pkr` computed field, §1 — the two numbers should match), and `margin_pkr = revenue_pkr - cost_pkr`.
9. `GET /reporting/margin?window_days=1` (a window before the sale happened, if timed right, or any window that provably excludes it) → confirm the item is absent from `entries` entirely (§2.6 — no row for an item with zero in-window sales, not a zero-value row).

---

## 8. Out of scope / open questions for later

- **`GET /reporting/reorder-priority` writes on every call, including background refetches** (§2.5) — flagged explicitly as a deliberate choice forced by `CLAUDE.md`'s "reporting has no mutations" frontend contract. The Phase 8 *frontend* spec should decide `reportingQueries.js`'s `useQuery` caching options for this one endpoint deliberately (e.g. disable `refetchOnWindowFocus`, or require an explicit user action like opening the `ReorderPriorityTable` screen to trigger it) rather than inheriting TanStack Query's defaults by accident. This backend spec makes the endpoint safe to call repeatedly (idempotent output) but does not itself decide how often the frontend should call it.
- **No historical/point-in-time balance statement** — `GET /reporting/balance-statement` always reads every `LedgerEntry` ever posted, "as of now." A `?as_of=` date filter (only counting entries up to that date) is a natural future extension if the business ever wants "what did we look like at the end of last month" — not built here because `PLAN.md`'s done-when line only asks "where does the business stand" (present tense), and it's additive (one more `WHERE entry_date <= :as_of` clause) whenever it's actually wanted.
- **`RecurringExpenseTemplate`/`Expense` spend has no dedicated section in the balance statement.** As `phase-7-backend.md §1`/§2.1 already established, an expense's ledger trail is entirely a byproduct of the `PaymentTransaction` it creates — it debits/credits the *paying account*, with no separate `"Expense"`-labeled ledger row anywhere. This means expense spend is already fully reflected inside `cash_accounts`' balances (the money genuinely left that account), but there is no P&L-style "total spent on expenses this month, by category" figure in this phase's balance statement — `PLAN.md`'s Phase 8 description doesn't ask for one explicitly (only "Balance statement," "Fast/slow-mover chart," "Reorder priority," "Margin report" are named), so it's treated as a real but separate future report (an `expense`-table `GROUP BY category_id` query, filtered to `status="confirmed"` per `phase-7-backend.md`'s own note that drafts never post to the ledger) rather than shoehorned into this phase's four endpoints.
- **Cargo/freight cost has no visibility of its own in any Phase 8 report.** Per §1, cargo cost never posts its own ledger entry — it's folded into `PurchaseOrderLine.landed_cost_pkr` before `StockLot`/`Inventory` is debited at receipt. The margin report (§4.5) therefore *does* implicitly include freight cost (it's baked into `unit_cost_pkr`), but there's no report answering "how much did we spend on cargo/freight this month" as its own line item — out of scope for the same reason as the expense breakdown above.
- **`Item.is_active`/discontinued items are not excluded from the margin report.** An item that sold during the window but was later deactivated still appears in `GET /reporting/margin` for that window (§4.5's query never filters on `Item.is_active`) — deliberate, since "did this item make money while it was being sold" doesn't stop being true after the item is discontinued; flagged in case a future consumer expects deactivated items to disappear from historical reports (they shouldn't, per `CLAUDE.md` §4's soft-delete/history rule).
- **No caching/materialization of any report.** Every endpoint recomputes its aggregate from scratch on every request — acceptable at this system's scale (a solo trading business, per `PLAN.md`'s opening line), flagged only so a future performance pass knows there is currently zero caching layer to reason about if these queries ever need to run against a much larger `ledger_entry`/`sales_order_line` table.

---

## 9. Implementation checklist

New:
- `backend/src/reporting/__init__.py`
- `backend/src/reporting/constants.py` — `DEFAULT_WINDOW_DAYS`, `MIN_WINDOW_DAYS`, `MAX_WINDOW_DAYS`
- `backend/src/reporting/utils.py` — `money`
- `backend/src/reporting/schemas.py` — all schemas in §3.2
- `backend/src/reporting/service.py` — `get_balance_statement`, `_rank_models_by_sell_through`, `get_sell_through`, `recalculate_reorder_priority`, `get_margin_report`
- `backend/src/reporting/router.py` — four `GET` routes (§5)

Changed:
- `backend/src/main.py` — one import, one `include_router` line (§5)

Not changed (confirmed, not assumed — §1, §2.1, §3.4):
- `backend/src/ledger/*`, `backend/src/parties/*`, `backend/src/payments/*`
- `backend/src/catalog/*` (except the *data* in its `model.priority` column, via a plain `UPDATE` — no code change to `catalog/`)
- `backend/src/inventory/*`, `backend/src/sales/*`, `backend/src/purchasing/*`, `backend/src/cargo/*`, `backend/src/expenses/*`, `backend/src/auth/*`
- `backend/src/crud.py`, `backend/src/exceptions.py`, `backend/src/pagination.py`, `backend/src/models.py`, `backend/src/database.py`, `backend/src/config.py`

No new package:
- No `reporting/models.py`, no `reporting/dependencies.py`, no `reporting/exceptions.py` (§2.1)
- No Alembic migration (§6)
- No `scripts/seed.py` changes (§7)
