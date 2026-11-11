import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listSalesOrders(params) {
  const { data } = await fetchClient.get(`/sales/sales-orders${buildQueryString(params)}`);
  return data;
}

export async function getSalesOrder(id) {
  const { data } = await fetchClient.get(`/sales/sales-orders/${id}`);
  return data;
}

export async function createSalesOrder(payload) {
  const { data } = await fetchClient.post('/sales/sales-orders', payload);
  return data;
}

// The Invoices list: one row per invoice (sale + its day-book entries), with whole-filter totals.
export async function listInvoices(params) {
  const { data } = await fetchClient.get(`/sales/sales-orders/invoices${buildQueryString(params)}`);
  return data;
}

// id -> invoice number for a batch of sales (the customer statement lists sales by id only).
// Repeated `ids` params, which is how FastAPI reads a list query param; not buildQueryString,
// which is shaped for page/page_size filters.
export async function getInvoiceNumbers(ids) {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append('ids', String(id)));
  const { data } = await fetchClient.get(`/sales/sales-orders/invoice-numbers?${params}`);
  return data; // [{ id, invoice_number }]
}

// Distinct invoice numbers for the Invoices dropdown (a sale or any day-book entry), most recent first; `search` narrows them.
export async function listInvoiceOptions(search) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  const { data } = await fetchClient.get(`/sales/sales-orders/invoice-options?${params}`);
  return data; // [{ invoice_number, sale_count, entry_count }]
}
