import { fetchClient } from '@/middleware/fetchClient';

// No buildQueryString reuse (utils/queryParams.js) — that helper always
// force-injects page/page_size into the query string (it's built for the
// paginated list endpoints every other domain has), and no endpoint here is
// paginated — they take a single `window_days`, or (profit-loss) explicit dates.
// A plain template literal / URLSearchParams is clearer than fighting a
// pagination-shaped helper into this shape.

export async function getBalanceStatement() {
  const { data } = await fetchClient.get('/reporting/balance-statement');
  return data; // BalanceStatementRead — no params, always "as of now"
}

export async function getSellThrough(windowDays) {
  const { data } = await fetchClient.get(`/reporting/sell-through?window_days=${windowDays}`);
  return data; // SellThroughRead
}

// Calling this WRITES Model.priority server-side, every time. Only ever
// invoke it from hooks/reportingHooks/reportingQueries.js's
// useRecalculateReorderPriority, and only ever fire that hook's refetch() from
// an explicit user action (components/reporting/ReorderPriorityTable.jsx's
// "Recalculate" button) — never from a query that runs on mount or refocus.
export async function recalculateReorderPriority(windowDays) {
  const { data } = await fetchClient.get(`/reporting/reorder-priority?window_days=${windowDays}`);
  return data; // ReorderPriorityRead
}

export async function getMarginReport(windowDays) {
  const { data } = await fetchClient.get(`/reporting/margin?window_days=${windowDays}`);
  return data; // MarginReportRead
}

// Read-only. dateFrom/dateTo are inclusive "YYYY-MM-DD" strings (utils/dateUtils.js's
// monthBounds builds them from a month picker). The backend validates the range.
export async function getProfitLoss({ dateFrom, dateTo, comparePrevious = false, includeUnitemised = false }) {
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
    compare_previous: String(comparePrevious),
    include_unitemised: String(includeUnitemised),
  });
  const { data } = await fetchClient.get(`/reporting/profit-loss?${params}`);
  return data; // ProfitLossRead
}

export async function getStockList(inStockOnly = true) {
  const { data } = await fetchClient.get(`/reporting/stock-list?in_stock_only=${inStockOnly}`);
  return data; // StockListRead
}
