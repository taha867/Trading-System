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
