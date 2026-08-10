import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listExpenseCategories(params) {
  const { data } = await fetchClient.get(`/expenses/expense-categories${buildQueryString(params)}`);
  return data;
}

export async function createExpenseCategory(payload) {
  const { data } = await fetchClient.post('/expenses/expense-categories', payload);
  return data;
}

export async function updateExpenseCategory({ id, ...payload }) {
  const { data } = await fetchClient.put(`/expenses/expense-categories/${id}`, payload);
  return data;
}

export async function deleteExpenseCategory(id) {
  await fetchClient.delete(`/expenses/expense-categories/${id}`);
}

export async function listRecurringExpenseTemplates(params) {
  const { data } = await fetchClient.get(`/expenses/recurring-expense-templates${buildQueryString(params)}`);
  return data;
}

// CrudDrawer's number-typed fields always hold '' (never null/undefined) when
// left empty (buildDefaultValues' fallback) — day_of_month is this domain's
// only optional int field wired through CrudDrawer, and the backend's
// `int | None` column rejects an empty string with a 422. Normalize '' to an
// explicit null before it ever leaves this service, rather than teaching the
// shared CrudDrawer.jsx about a single field's nullability.
function sanitizeDayOfMonth(payload) {
  return { ...payload, day_of_month: payload.day_of_month === '' ? null : payload.day_of_month };
}

export async function createRecurringExpenseTemplate(payload) {
  const { data } = await fetchClient.post('/expenses/recurring-expense-templates', sanitizeDayOfMonth(payload));
  return data;
}

export async function updateRecurringExpenseTemplate({ id, ...payload }) {
  const { data } = await fetchClient.put(`/expenses/recurring-expense-templates/${id}`, sanitizeDayOfMonth(payload));
  return data;
}

export async function deleteRecurringExpenseTemplate(id) {
  await fetchClient.delete(`/expenses/recurring-expense-templates/${id}`);
}

// No ?period= passed — the backend defaults to the current month (no
// back-dated-generation UI in this phase).
export async function generateExpenseFromTemplate(templateId) {
  const { data } = await fetchClient.post(`/expenses/recurring-expense-templates/${templateId}/generate`);
  return data; // ExpenseRead, the new draft
}

export async function listExpenses(params) {
  const { data } = await fetchClient.get(`/expenses/entries${buildQueryString(params)}`);
  return data;
}

export async function createExpense(payload) {
  const { data } = await fetchClient.post('/expenses/entries', payload);
  return data;
}

export async function confirmExpense(id) {
  const { data } = await fetchClient.post(`/expenses/entries/${id}/confirm`);
  return data;
}

export async function discardExpense(id) {
  await fetchClient.delete(`/expenses/entries/${id}`);
}
