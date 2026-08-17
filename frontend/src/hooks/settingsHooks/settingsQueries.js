import { useQuery } from '@tanstack/react-query';
import { settingsKeys } from '@/utils/queryKeys';
import { getSetting } from '@/services/settingsService';

export function useSetting() {
  return useQuery({
    queryKey: settingsKeys.detail(),
    queryFn: getSetting,
  });
}
