import { useMutation, useQueryClient } from '@tanstack/react-query';
import { exchangeRateKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import * as purchasingService from '@/services/purchasingService';

export function useCreateExchangeRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: purchasingService.createExchangeRate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: exchangeRateKeys.lists() }),
  });
}

export function useUpdateExchangeRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: purchasingService.updateExchangeRate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: exchangeRateKeys.lists() }),
  });
}

export function useDeleteExchangeRate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: purchasingService.deleteExchangeRate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: exchangeRateKeys.lists() }),
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: purchasingService.createPurchaseOrder,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: purchaseOrderKeys.lists() }),
  });
}
