import { useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsKeys } from '@/utils/queryKeys';
import { updateSetting } from '@/services/settingsService';

export function useUpdateSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateSetting,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: settingsKeys.detail() }),
  });
}
