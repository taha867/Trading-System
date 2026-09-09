import { useQuery } from '@tanstack/react-query';
import { exchangeRateKeys, purchaseOrderKeys } from '@/utils/queryKeys';
import { listExchangeRates, listPurchaseOrders, getPurchaseOrder } from '@/services/purchasingService';

export function useExchangeRates(params) {
  return useQuery({
    queryKey: exchangeRateKeys.list(params),
    queryFn: () => listExchangeRates(params),
  });
}

// GET /purchasing/exchange-rates?rate_date= filters server-side (an exact-match
// date_filters entry on the generic CRUD factory) — no more fetching a fixed
// page and hoping the target date is in the first 100 rows.
export function useExchangeRateForDate(rateDate) {
  const query = useExchangeRates({ page: 1, page_size: 1, rate_date: rateDate });
  const rate = query.data?.items?.[0] ?? null;
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

// GET /purchasing/purchase-orders?status= now filters server-side — draft POs
// realistically never number in the hundreds at once, so page_size=100 here
// is a reasonable cap, not a silent-truncation risk like the old unfiltered fetch.
export function useDraftPurchaseOrders() {
  const query = usePurchaseOrders({ page: 1, page_size: 100, status: 'draft' });
  const draftOrders = query.data?.items ?? [];
  return { ...query, draftOrders };
}
