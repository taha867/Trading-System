import { useQuery } from '@tanstack/react-query';
import { stockLotKeys, stockMovementKeys } from '@/utils/queryKeys';
import { listStockLots, getStockLot, listStockMovements } from '@/services/inventoryService';

export function useStockLots(params) {
  return useQuery({ queryKey: stockLotKeys.list(params), queryFn: () => listStockLots(params) });
}

export function useStockLot(id) {
  return useQuery({
    queryKey: stockLotKeys.detail(id),
    queryFn: () => getStockLot(id),
    enabled: Boolean(id),
  });
}

export function useStockMovements(params) {
  return useQuery({ queryKey: stockMovementKeys.list(params), queryFn: () => listStockMovements(params) });
}

// Derived, not a separate backend call — no ?purchase_order_line_id= filter exists on
// GET /inventory/stock-lots, so this fetches every lot and returns the set of
// already-received line ids, for PurchaseOrderDetail's per-line Receive button.
//
// include_depleted: true is not optional here — a lot fully consumed by a future
// Phase 4 sale must still count as "this line was received." Dropping this flag would
// make an already-received line's Receive button silently reappear once its lot hits
// zero, which is wrong: receipt state is "does a lot exist," never "is it non-empty."
export function useReceivedLineIds() {
  const query = useStockLots({ page: 1, page_size: 100, include_depleted: true });
  const ids = new Set((query.data?.items ?? []).map((lot) => lot.purchase_order_line_id));
  return { ...query, ids };
}
