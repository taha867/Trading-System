import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listPaymentMethods(params) {
  const { data } = await fetchClient.get(`/payments/payment-methods${buildQueryString(params)}`);
  return data; // { items, total, page, page_size }
}

export async function createPaymentMethod(payload) {
  const { data } = await fetchClient.post('/payments/payment-methods', payload);
  return data;
}

export async function updatePaymentMethod({ id, ...payload }) {
  const { data } = await fetchClient.put(`/payments/payment-methods/${id}`, payload);
  return data;
}

export async function deletePaymentMethod(id) {
  await fetchClient.delete(`/payments/payment-methods/${id}`);
}

export async function listPaymentAccounts(params) {
  const { data } = await fetchClient.get(`/payments/payment-accounts${buildQueryString(params)}`);
  return data; // { items, total, page, page_size }
}

export async function createPaymentAccount(payload) {
  const { data } = await fetchClient.post('/payments/payment-accounts', payload);
  return data;
}

export async function updatePaymentAccount({ id, ...payload }) {
  const { data } = await fetchClient.put(`/payments/payment-accounts/${id}`, payload);
  return data;
}

export async function deletePaymentAccount(id) {
  await fetchClient.delete(`/payments/payment-accounts/${id}`);
}

// Returns a plain array, not {items,total,...} — GET /payment-accounts/balances is
// a full active-accounts dump, not paginated. Don't wrap or paginate this.
export async function getPaymentAccountBalances() {
  const { data } = await fetchClient.get('/payments/payment-accounts/balances');
  return data;
}

export async function listPaymentTransactions(params) {
  const { data } = await fetchClient.get(`/payments/payment-transactions${buildQueryString(params)}`);
  return data;
}

export async function createPaymentTransaction(payload) {
  const { data } = await fetchClient.post('/payments/payment-transactions', payload);
  return data;
}
