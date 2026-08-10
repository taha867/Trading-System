import { useMutation, useQueryClient } from '@tanstack/react-query';
import { itemKeys } from '@/utils/queryKeys';
import * as catalogService from '@/services/catalogService';

export function useCreateItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.createItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemKeys.lists() }),
  });
}

export function useUpdateItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.updateItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemKeys.lists() }),
  });
}

export function useDeleteItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.deleteItem,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: itemKeys.lists() }),
  });
}
