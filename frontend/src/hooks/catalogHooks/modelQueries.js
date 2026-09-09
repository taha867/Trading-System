import { useQuery } from '@tanstack/react-query';
import { modelKeys } from '@/utils/queryKeys';
import { getModel, listModels } from '@/services/catalogService';

export function useModels(params) {
  return useQuery({
    queryKey: modelKeys.list(params),
    queryFn: () => listModels(params),
  });
}

// Resolves one model by id regardless of what a search-filtered picker's
// current results contain — same reasoning as catalogHooks/itemQueries.js's useItem.
export function useModel(id) {
  return useQuery({
    queryKey: modelKeys.detail(id),
    queryFn: () => getModel(id),
    enabled: Boolean(id),
  });
}
