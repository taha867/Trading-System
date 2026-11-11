import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { exchangeRateKeys, purchaseOrderKeys, purchaseGroupKeys } from '@/utils/queryKeys';
import { PURCHASE_ORDER_STATUS } from '@/utils/constants';
import {
  listExchangeRates,
  listPurchaseOrders,
  getPurchaseOrder,
  listPurchaseInvoiceOptions,
  getPurchaseInvoiceNumbers,
  listPurchaseGroups,
} from '@/services/purchasingService';

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

// keepPrevious is opt-in: the filtered list screen wants the last results to stay on screen while
// the next set loads, but the cargo and payment pickers that share this hook behave as before.
export function usePurchaseOrders(params, { enabled = true, keepPrevious = false } = {}) {
  return useQuery({
    queryKey: purchaseOrderKeys.list(params),
    queryFn: () => listPurchaseOrders(params),
    enabled,
    placeholderData: keepPrevious ? keepPreviousData : undefined,
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
  const query = usePurchaseOrders({ page: 1, page_size: 100, status: PURCHASE_ORDER_STATUS.DRAFT });
  const draftOrders = query.data?.items ?? [];
  return { ...query, draftOrders };
}

export function usePurchaseInvoiceOptions(search) {
  return useQuery({
    queryKey: purchaseOrderKeys.invoiceOptions(search),
    queryFn: () => listPurchaseInvoiceOptions(search),
    placeholderData: keepPreviousData,
  });
}

// Returns { [orderId]: invoiceNumber | null } for the given purchase order ids; idle when there are none.
export function usePurchaseInvoiceNumbers(ids) {
  const sortedIds = [...ids].sort((a, b) => a - b);
  return useQuery({
    queryKey: purchaseOrderKeys.invoiceNumbers(sortedIds),
    queryFn: () => getPurchaseInvoiceNumbers(sortedIds),
    enabled: sortedIds.length > 0,
    select: (rows) => Object.fromEntries(rows.map((row) => [row.id, row.invoice_number])),
  });
}

// One row per supplier invoice with its payable-only entries under it; keepPreviousData like the other lists.
export function usePurchaseGroups(params) {
  return useQuery({
    queryKey: purchaseGroupKeys.list(params),
    queryFn: () => listPurchaseGroups(params),
    placeholderData: keepPreviousData,
  });
}
