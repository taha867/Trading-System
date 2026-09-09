import { useQuery } from '@tanstack/react-query';
import { itemKeys } from '@/utils/queryKeys';
import { getItem, listItems } from '@/services/catalogService';

export function useItems(params) {
  return useQuery({
    queryKey: itemKeys.list(params),
    queryFn: () => listItems(params),
  });
}

// Resolves one item by id regardless of what a search-filtered picker's
// current results contain — a combobox needs the selected item's own label
// even after its search text no longer matches it.
export function useItem(id) {
  return useQuery({
    queryKey: itemKeys.detail(id),
    queryFn: () => getItem(id),
    enabled: Boolean(id),
  });
}
