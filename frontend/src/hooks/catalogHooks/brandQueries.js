import { useQuery } from '@tanstack/react-query';
import { brandKeys } from '@/utils/queryKeys';
import { listBrands } from '@/services/catalogService';

export function useBrands(params) {
  return useQuery({
    queryKey: brandKeys.list(params),
    queryFn: () => listBrands(params),
  });
}
