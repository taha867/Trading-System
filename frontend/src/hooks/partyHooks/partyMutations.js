import { useMutation, useQueryClient } from '@tanstack/react-query';
import { partyKeys } from '@/utils/queryKeys';
import * as partyService from '@/services/partyService';

export function useCreateParty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: partyService.createParty,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partyKeys.lists() }),
  });
}

export function useUpdateParty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: partyService.updateParty,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partyKeys.lists() }),
  });
}

export function useDeactivateParty() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: partyService.deactivateParty,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: partyKeys.lists() }),
  });
}
