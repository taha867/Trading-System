import { useQuery } from '@tanstack/react-query';
import { itemKeys } from '@/utils/queryKeys';
import { listItems } from '@/services/catalogService';

export function useItems(params) {
  return useQuery({
    queryKey: itemKeys.list(params),
    queryFn: () => listItems(params),
  });
}
