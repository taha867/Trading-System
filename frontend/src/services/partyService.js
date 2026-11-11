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

// `dateFrom` / `dateTo` (YYYY-MM-DD, both optional): the statement for that period, with the opening balance as of dateFrom.
export async function getPartyStatement(id, { dateFrom, dateTo } = {}) {
  const query = new URLSearchParams();
  if (dateFrom) query.set('date_from', dateFrom);
  if (dateTo) query.set('date_to', dateTo);
  const suffix = query.size ? `?${query}` : '';
  const { data } = await fetchClient.get(`/parties/${id}/statement${suffix}`);
  return data;
}
