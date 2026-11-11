import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { reportingKeys } from '@/utils/queryKeys';
import {
  getBalanceStatement,
  getSellThrough,
  recalculateReorderPriority,
  getMarginReport,
  getProfitLoss,
  getStockList,
} from '@/services/reportingService';

export function useBalanceStatement() {
  return useQuery({
    queryKey: reportingKeys.balanceStatement(),
    queryFn: getBalanceStatement,
  });
}

// `window` is a number of days, or { dateFrom, dateTo } (both required, else the query waits).
const windowReady = (window) => typeof window === 'number' || Boolean(window?.dateFrom && window?.dateTo);

export function useSellThrough(window) {
  return useQuery({
    queryKey: reportingKeys.sellThrough(window),
    queryFn: () => getSellThrough(window),
    enabled: windowReady(window),
    placeholderData: keepPreviousData,
  });
}

export function useMarginReport(window) {
  return useQuery({
    queryKey: reportingKeys.margin(window),
    queryFn: () => getMarginReport(window),
    enabled: windowReady(window),
    placeholderData: keepPreviousData,
  });
}

// keepPreviousData: paging between months keeps the last statement on screen
// while the next one loads, instead of flashing back to the loading state.
export function useProfitLoss({ dateFrom, dateTo, comparePrevious = false, includeUnitemised = false }) {
  return useQuery({
    queryKey: reportingKeys.profitLoss(dateFrom, dateTo, comparePrevious, includeUnitemised),
    queryFn: () => getProfitLoss({ dateFrom, dateTo, comparePrevious, includeUnitemised }),
    enabled: Boolean(dateFrom && dateTo),
    placeholderData: keepPreviousData,
  });
}

// Deliberately lazy — enabled:false means this never fetches on mount and
// never refetches in the background; refetchOnWindowFocus:false is redundant
// with enabled:false today but kept as a second guard against a future edit
// accidentally flipping `enabled` on. The ONLY caller of this hook's `refetch`
// is components/reporting/ReorderPriorityTable.jsx's "Recalculate" button —
// nothing else should ever import recalculateReorderPriority directly.
//
// No onSuccess/onError here: TanStack Query v5 removed those callbacks from
// useQuery entirely (kept only on useMutation). Whatever needs to run after a
// successful recalculation (invalidating Catalog's Model list) happens in the
// component, after awaiting the refetch() promise this hook returns.
export function useRecalculateReorderPriority(windowDays) {
  return useQuery({
    queryKey: reportingKeys.reorderPriority(windowDays),
    queryFn: () => recalculateReorderPriority(windowDays),
    enabled: false,
    refetchOnWindowFocus: false,
  });
}

export function useStockList(inStockOnly = true) {
  return useQuery({
    queryKey: reportingKeys.stockList(inStockOnly),
    queryFn: () => getStockList(inStockOnly),
  });
}
