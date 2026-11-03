# Monthly Profit & Loss — Backend Plan

Implements `.claude/specs/monthly-profit-loss.md` §3. All changes are in `backend/src/reporting/`. Read-only endpoint, no migration, no schema change.

## Decisions (from the spec)
- Accrual basis. Revenue and COGS by `SalesOrder.order_date`; stock loss by `StockMovement.movement_date`; expenses by `Expense.expense_date`, `status='confirmed'` only.
- `net = (revenue − cogs) − stock_loss − confirmed_expenses`. Purchases, payments and receipts are excluded.
- Unitemised sales (`SalesLogException`) reported separately, excluded from profit by default (`include_unitemised=false`).
- Endpoint takes `date_from` / `date_to`; it never calls `date.today()`.
- Built from domain tables, not the ledger (the ledger has no revenue/COGS/expense accounts).

## Steps
1. `constants.py` — `MAX_REPORT_RANGE_DAYS = 366`.
2. `exceptions.py` (new) — `InvalidReportPeriod(AppException)`, status 422.
3. `schemas.py` — `ExpenseCategoryTotalRead`, `UnitemisedSalesKindRead`, `ProfitLossPeriodRead`, `ProfitLossRead` (money is `Decimal`).
4. `utils.py` — keep `money()`; add pure helpers `validate_period` and `previous_period`.
5. `service.py` — extract `_revenue_by_item_subquery` / `_cost_by_item_subquery` from `get_margin_report` and reuse them in the P&L so the two reconcile by construction; add `_compute_period` and `get_profit_loss`. No `commit()`.
6. `router.py` — `GET /reporting/profit-loss` with `date_from`, `date_to`, `compare_previous`, `include_unitemised`; thin, `response_model=ProfitLossRead`, auth via `get_current_user`.

## Verification
- Hand-total a real month; compare each figure through `/docs`.
- `gross_profit_pkr` equals Margin-by-Item `total_margin_pkr` for the same dates; the margin report's output is unchanged by the refactor.
- Empty month → zeros; `date_from > date_to` and range > 366 days → 422; previous period across Jan→Dec and February.
- No DB writes, no migration.

## Open risks
`SalesLogException` semantics and sign; sale lines without lot rows; local purchases entered as expenses; server timezone; restrict to admins once roles exist.
