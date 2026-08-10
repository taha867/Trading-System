import { useQuery } from '@tanstack/react-query';
import { modelKeys } from '@/utils/queryKeys';
import { listModels } from '@/services/catalogService';

export function useModels(params) {
  return useQuery({
    queryKey: modelKeys.list(params),
    queryFn: () => listModels(params),
  });
}
