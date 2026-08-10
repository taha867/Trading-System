import { useMutation, useQueryClient } from '@tanstack/react-query';
import { salesOrderKeys, stockLotKeys, partyKeys } from '@/utils/queryKeys';
import * as salesService from '@/services/salesService';

export function useCreateSalesOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: salesService.createSalesOrder,
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: salesOrderKeys.lists() });
      // A sale consumes StockLot.qty_remaining via FIFO (phase-4-backend spec §2.4) —
      // the inventory view must reflect the drawdown without a manual refresh.
      // Invalidate the whole key space (lists + any cached detail), same reasoning
      // the phase-3 spec used for a receive's effect on purchaseOrderKeys.
      queryClient.invalidateQueries({ queryKey: stockLotKeys.all });
      // Posts one LedgerEntry against this party (phase-4-backend spec §2.6) — if
      // their statement is open in another tab, it must pick up the new entry and
      // balance.
      queryClient.invalidateQueries({ queryKey: partyKeys.statement(variables.party_id) });
    },
  });
}
