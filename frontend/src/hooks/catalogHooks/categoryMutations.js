import { useMutation, useQueryClient } from '@tanstack/react-query';
import { categoryKeys } from '@/utils/queryKeys';
import * as catalogService from '@/services/catalogService';

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.createCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoryKeys.lists() }),
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.updateCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoryKeys.lists() }),
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.deleteCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: categoryKeys.lists() }),
  });
}
