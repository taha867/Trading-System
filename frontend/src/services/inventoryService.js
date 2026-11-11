import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listStockLots({
  page,
  page_size,
  item_id,
  include_depleted,
  category_id,
  brand_id,
  model_id,
} = {}) {
  const qs = buildQueryString({
    page,
    page_size,
    item_id,
    include_depleted: include_depleted || undefined,
    category_id,
    brand_id,
    model_id,
  });
  const { data } = await fetchClient.get(`/inventory/stock-lots${qs}`);
  return data;
}

// What a sale of each item can draw on: its own pieces, and the pieces of other items that also fit its phone.
export async function getItemAvailability(itemIds) {
  const qs = `?${itemIds.map((id) => `item_ids=${encodeURIComponent(id)}`).join('&')}`;
  const { data } = await fetchClient.get(`/inventory/availability${qs}`);
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

export async function listStockMovements({
  page,
  page_size,
  stock_lot_id,
  movement_type,
  category_id,
  brand_id,
  model_id,
} = {}) {
  const qs = buildQueryString({ page, page_size, stock_lot_id, movement_type, category_id, brand_id, model_id });
  const { data } = await fetchClient.get(`/inventory/stock-movements${qs}`);
  return data;
}

export async function createStockMovement(payload) {
  const { data } = await fetchClient.post('/inventory/stock-movements', payload);
  return data;
}

export async function markStockLotDamaged(payload) {
  const { data } = await fetchClient.post('/inventory/stock-movements/damage', payload);
  return data;
}
