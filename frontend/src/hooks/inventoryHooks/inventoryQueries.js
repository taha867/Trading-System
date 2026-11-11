import { useQuery } from '@tanstack/react-query';
import { stockLotKeys, stockMovementKeys } from '@/utils/queryKeys';
import { listStockLots, getStockLot, getItemAvailability, listStockMovements } from '@/services/inventoryService';

export function useStockLots(params) {
  return useQuery({ queryKey: stockLotKeys.list(params), queryFn: () => listStockLots(params) });
}

// Own pieces + pieces of "also fits" items for each item id (sorted and de-duplicated so the key is stable).
export function useItemAvailability(itemIds) {
  const ids = [...new Set(itemIds.map(Number).filter(Boolean))].sort((a, b) => a - b);
  return useQuery({
    queryKey: stockLotKeys.availability(ids),
    queryFn: () => getItemAvailability(ids),
    enabled: ids.length > 0,
  });
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
