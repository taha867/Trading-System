import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listStockLots({ page, page_size, item_id, include_depleted } = {}) {
  const qs = buildQueryString({ page, page_size, item_id, include_depleted: include_depleted || undefined });
  const { data } = await fetchClient.get(`/inventory/stock-lots${qs}`);
  return data;
}

export async function getStockLot(id) {
  const { data } = await fetchClient.get(`/inventory/stock-lots/${id}`);
  return data;
}

export async function receiveStockLot(payload) {
  const { data } = await fetchClient.post('/inventory/stock-lots', payload);
  return data;
}

export async function listStockMovements({ page, page_size, stock_lot_id } = {}) {
  const qs = buildQueryString({ page, page_size, stock_lot_id });
  const { data } = await fetchClient.get(`/inventory/stock-movements${qs}`);
  return data;
}

export async function createStockMovement(payload) {
  const { data } = await fetchClient.post('/inventory/stock-movements', payload);
  return data;
}
