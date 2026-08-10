import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listParties(params) {
  const { data } = await fetchClient.get(`/parties${buildQueryString(params)}`);
  return data;
}

export async function createParty(payload) {
  const { data } = await fetchClient.post('/parties', payload);
  return data;
}

export async function updateParty({ id, ...payload }) {
  const { data } = await fetchClient.put(`/parties/${id}`, payload);
  return data;
}

export async function deactivateParty(id) {
  await fetchClient.delete(`/parties/${id}`);
}

export async function getPartyStatement(id) {
  const { data } = await fetchClient.get(`/parties/${id}/statement`);
  return data;
}
