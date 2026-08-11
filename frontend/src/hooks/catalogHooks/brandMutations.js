import { useMutation, useQueryClient } from '@tanstack/react-query';
import { brandKeys } from '@/utils/queryKeys';
import * as catalogService from '@/services/catalogService';

export function useCreateBrand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.createBrand,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: brandKeys.lists() }),
  });
}

export function useUpdateBrand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.updateBrand,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: brandKeys.lists() }),
  });
}

export function useDeleteBrand() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.deleteBrand,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: brandKeys.lists() }),
  });
}
