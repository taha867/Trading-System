import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { salesOrderKeys, invoiceKeys } from '@/utils/queryKeys';
import {
  listSalesOrders,
  getSalesOrder,
  listInvoices,
  getInvoiceNumbers,
  listInvoiceOptions,
} from '@/services/salesService';

// keepPreviousData: typing in a filter keeps the last results on screen while the next set
// loads, instead of flashing back to the loading state on every change.
export function useSalesOrders(params, { enabled = true } = {}) {
  return useQuery({
    queryKey: salesOrderKeys.list(params),
    queryFn: () => listSalesOrders(params),
    enabled,
    placeholderData: keepPreviousData,
  });
}

export function useSalesOrder(id) {
  return useQuery({
    queryKey: salesOrderKeys.detail(id),
    queryFn: () => getSalesOrder(id),
    enabled: Boolean(id),
  });
}

// One row per invoice with its day-book entries under it; keepPreviousData like the other lists.
export function useInvoices(params) {
  return useQuery({
    queryKey: invoiceKeys.list(params),
    queryFn: () => listInvoices(params),
    placeholderData: keepPreviousData,
  });
}

// Returns { [saleId]: invoiceNumber | null } for the given sale ids; idle when there are none.
export function useInvoiceNumbers(ids) {
  const sortedIds = [...ids].sort((a, b) => a - b);
  return useQuery({
    queryKey: salesOrderKeys.invoiceNumbers(sortedIds),
    queryFn: () => getInvoiceNumbers(sortedIds),
    enabled: sortedIds.length > 0,
    select: (rows) => Object.fromEntries(rows.map((row) => [row.id, row.invoice_number])),
  });
}

export function useInvoiceOptions(search) {
  return useQuery({
    queryKey: salesOrderKeys.invoiceOptions(search),
    queryFn: () => listInvoiceOptions(search),
    placeholderData: keepPreviousData,
  });
}
