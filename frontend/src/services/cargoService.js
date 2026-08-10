import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listCargoModes(params) {
  const { data } = await fetchClient.get(`/cargo/modes${buildQueryString(params)}`);
  return data;
}

export async function createCargoMode(payload) {
  const { data } = await fetchClient.post('/cargo/modes', payload);
  return data;
}

export async function updateCargoMode({ id, ...payload }) {
  const { data } = await fetchClient.put(`/cargo/modes/${id}`, payload);
  return data;
}

export async function deleteCargoMode(id) {
  await fetchClient.delete(`/cargo/modes/${id}`);
}

export async function listCargoCostBases(params) {
  const { data } = await fetchClient.get(`/cargo/cost-bases${buildQueryString(params)}`);
  return data;
}

export async function createCargoCostBasis(payload) {
  const { data } = await fetchClient.post('/cargo/cost-bases', payload);
  return data;
}

export async function updateCargoCostBasis({ id, ...payload }) {
  const { data } = await fetchClient.put(`/cargo/cost-bases/${id}`, payload);
  return data;
}

export async function deleteCargoCostBasis(id) {
  await fetchClient.delete(`/cargo/cost-bases/${id}`);
}

export async function listCargoShipments(params) {
  const { data } = await fetchClient.get(`/cargo/shipments${buildQueryString(params)}`);
  return data;
}

export async function getCargoShipment(id) {
  const { data } = await fetchClient.get(`/cargo/shipments/${id}`);
  return data;
}

export async function createCargoShipment(payload) {
  const { data } = await fetchClient.post('/cargo/shipments', payload);
  return data;
}
