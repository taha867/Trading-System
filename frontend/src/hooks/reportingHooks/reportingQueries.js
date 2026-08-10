import { useQuery } from '@tanstack/react-query';
import { reportingKeys } from '@/utils/queryKeys';
import {
  getBalanceStatement,
  getSellThrough,
  recalculateReorderPriority,
  getMarginReport,
} from '@/services/reportingService';

export function useBalanceStatement() {
  return useQuery({
    queryKey: reportingKeys.balanceStatement(),
    queryFn: getBalanceStatement,
  });
}

export function useSellThrough(windowDays) {
  return useQuery({
    queryKey: reportingKeys.sellThrough(windowDays),
    queryFn: () => getSellThrough(windowDays),
  });
}

export function useMarginReport(windowDays) {
  return useQuery({
    queryKey: reportingKeys.margin(windowDays),
    queryFn: () => getMarginReport(windowDays),
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
