import { useMutation, useQueryClient } from '@tanstack/react-query';
import { modelKeys } from '@/utils/queryKeys';
import * as catalogService from '@/services/catalogService';

export function useCreateModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.createModel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: modelKeys.lists() }),
  });
}

export function useUpdateModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.updateModel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: modelKeys.lists() }),
  });
}

export function useDeleteModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: catalogService.deleteModel,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: modelKeys.lists() }),
  });
}
