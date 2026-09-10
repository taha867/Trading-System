import { useMutation, useQueryClient } from '@tanstack/react-query';
import { stockLotKeys, stockMovementKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import * as inventoryService from '@/services/inventoryService';

export function useReceiveStockLot() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inventoryService.receiveStockLot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: stockLotKeys.lists() });
      // A receive can flip the parent PO's status to "received" once its last line
      // lands — invalidate the whole purchaseOrders key space (lists + every cached
      // detail) so an open PurchaseOrderDetail tab picks this up, same reasoning as
      // the phase-2 spec's cargo-shipment-create invalidation.
      queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.all });
    },
  });
}

export function useCreateStockMovement() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inventoryService.createStockMovement,
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: stockLotKeys.lists() });
      queryClient.invalidateQueries({ queryKey: stockLotKeys.detail(variables.stock_lot_id) });
      queryClient.invalidateQueries({ queryKey: stockMovementKeys.lists() });
    },
  });
}

// Same invalidation shape as useCreateStockMovement above — marking a lot
// damaged reduces its qty_remaining exactly like a generic adjustment does,
// just through its own dedicated endpoint (see inventory/service.py's
// mark_stock_lot_damaged) so it's precisely queryable as its own movement_type
// instead of a free-text "reason" on a generic adjustment.
export function useMarkStockLotDamaged() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: inventoryService.markStockLotDamaged,
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: stockLotKeys.lists() });
      queryClient.invalidateQueries({ queryKey: stockLotKeys.detail(variables.stock_lot_id) });
      queryClient.invalidateQueries({ queryKey: stockMovementKeys.lists() });
    },
  });
}
