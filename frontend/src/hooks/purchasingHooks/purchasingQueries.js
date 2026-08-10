import { useQuery } from '@tanstack/react-query';
import { exchangeRateKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import { listExchangeRates, listPurchaseOrders, getPurchaseOrder } from '@/services/purchasingService';

export function useExchangeRates(params) {
  return useQuery({
    queryKey: exchangeRateKeys.list(params),
    queryFn: () => listExchangeRates(params),
  });
}

// Derived, not a separate backend call — no ?rate_date= filter exists, so this
// fetches one page_size=100 page and searches client-side for an exact match.
export function useExchangeRateForDate(rateDate) {
  const query = useExchangeRates({ page: 1, page_size: 100 });
  const rate = query.data?.items?.find((r) => r.rate_date === rateDate) ?? null;
  return { ...query, rate };
}

export function usePurchaseOrders(params) {
  return useQuery({
    queryKey: purchaseOrderKeys.list(params),
    queryFn: () => listPurchaseOrders(params),
  });
}

export function usePurchaseOrder(id) {
  return useQuery({
    queryKey: purchaseOrderKeys.detail(id),
    queryFn: () => getPurchaseOrder(id),
    enabled: Boolean(id),
  });
}

// Derived, not a separate backend call — no ?status= filter exists on
// GET /purchasing/purchase-orders (phase-2-frontend spec §1.1), so this fetches one
// page_size=100 page and filters client-side, same pattern as useExchangeRateForDate.
export function useDraftPurchaseOrders() {
  const query = usePurchaseOrders({ page: 1, page_size: 100 });
  const draftOrders = (query.data?.items ?? []).filter((order) => order.status === 'draft');
  return { ...query, draftOrders };
}
