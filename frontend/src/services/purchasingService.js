import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listExchangeRates(params) {
  const { data } = await fetchClient.get(`/purchasing/exchange-rates${buildQueryString(params)}`);
  return data; // { items, total, page, page_size }
}

export async function createExchangeRate(payload) {
  const { data } = await fetchClient.post('/purchasing/exchange-rates', payload);
  return data;
}

export async function updateExchangeRate({ id, ...payload }) {
  const { data } = await fetchClient.put(`/purchasing/exchange-rates/${id}`, payload);
  return data;
}

export async function deleteExchangeRate(id) {
  await fetchClient.delete(`/purchasing/exchange-rates/${id}`);
}

export async function listPurchaseOrders(params) {
  const { data } = await fetchClient.get(`/purchasing/purchase-orders${buildQueryString(params)}`);
  return data;
}

export async function getPurchaseOrder(id) {
  const { data } = await fetchClient.get(`/purchasing/purchase-orders/${id}`);
  return data;
}

export async function createPurchaseOrder(payload) {
  const { data } = await fetchClient.post('/purchasing/purchase-orders', payload);
  return data;
}

// Distinct invoice numbers for the Purchases dropdown (an order or a payable-only entry), most recent first; `search` narrows them.
export async function listPurchaseInvoiceOptions(search) {
  const params = new URLSearchParams();
  if (search) params.set('search', search);
  const { data } = await fetchClient.get(`/purchasing/purchase-orders/invoice-options?${params}`);
  return data; // [{ invoice_number, order_count, entry_count }]
}

// id -> invoice number for a batch of purchase orders (the vendor statement lists orders by id only).
// Repeated `ids` params, which is how FastAPI reads a list query param; not buildQueryString, which
// is shaped for page/page_size filters.
export async function getPurchaseInvoiceNumbers(ids) {
  const params = new URLSearchParams();
  ids.forEach((id) => params.append('ids', String(id)));
  const { data } = await fetchClient.get(`/purchasing/purchase-orders/invoice-numbers?${params}`);
  return data; // [{ id, invoice_number }]
}

// The Purchases list: one row per supplier invoice (order(s) + payable-only entries), with whole-filter totals.
export async function listPurchaseGroups(params) {
  const { data } = await fetchClient.get(`/purchasing/purchase-orders/purchases${buildQueryString(params)}`);
  return data;
}
