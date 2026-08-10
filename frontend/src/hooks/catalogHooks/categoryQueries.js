import { useQuery } from '@tanstack/react-query';
import { categoryKeys } from '@/utils/queryKeys';
import { listCategories } from '@/services/catalogService';

export function useCategories(params) {
  return useQuery({
    queryKey: categoryKeys.list(params),
    queryFn: () => listCategories(params),
  });
}
