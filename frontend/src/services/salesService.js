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

export async function listSalesLogExceptions(params) {
  const { data } = await fetchClient.get(`/sales/sales-log-exceptions${buildQueryString(params)}`);
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
