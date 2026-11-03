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
