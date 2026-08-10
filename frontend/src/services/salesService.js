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
