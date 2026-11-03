# Monthly Profit & Loss — Frontend Plan

Implements `.claude/specs/monthly-profit-loss.md` §4. All changes are under `frontend/src/`. Layering per `CLAUDE.md` §3.4; use the `frontend-design-system` skill for visuals.

## Steps
1. `utils/dateUtils.js` (new) — `currentMonth()` (local time, not `toISOString`), `monthBounds(month)`, `shiftMonth(month, delta)`. `ExpenseList.jsx` imports `monthBounds` instead of its private `monthToDateRange`.
2. `services/reportingService.js` — `getProfitLoss({ dateFrom, dateTo, comparePrevious, includeUnitemised })` with a plain template string (not `buildQueryString`).
3. `utils/queryKeys.js` — `reportingKeys.profitLoss(...)`.
4. `hooks/reportingHooks/reportingQueries.js` — `useProfitLoss(params)`.
5. `components/common/StatCard.jsx` — optional `valueClassName` (for a negative net profit).
6. `components/reporting/ProfitLossStatement.jsx` (new) — month picker, previous/next, compare toggle, four stat cards, statement table (`overflow-x-auto` from `sm`, stacked cards below), expense rows per category, "Not included" notice, API warnings, print button. Money only through `CurrencyAmount`.
7. `containers/ReportsContainer.jsx` + `pages/ReportsPage.jsx` (new) — month kept in `?month=YYYY-MM`.
8. `App.jsx` — `/reports` inside the `ProtectedRoute` group.
9. `utils/constants.js` — `NAV_LINKS` entry for Reports.
10. Print — `print:hidden` on `Sidebar`, `BottomNav`, `Navbar` and page controls.
11. Related fixes — label the `ExpenseList` total "including drafts"; note on `MarginReportTable` that it is a rolling window.

## Verification
- `npm run build` and `npm run lint`.
- `/reports` at 375, 768 and 1280 px; compare toggle; Jan→Dec; print preview.
- Figures match the sales order screens and the Expenses screen for the same month (confirmed only).
