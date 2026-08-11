import { fetchClient } from '@/middleware/fetchClient';
import { buildQueryString } from '@/utils/queryParams';

export async function listCategories(params) {
  const { data } = await fetchClient.get(`/catalog/categories${buildQueryString(params)}`);
  return data;
}

export async function createCategory(payload) {
  const { data } = await fetchClient.post('/catalog/categories', payload);
  return data;
}

export async function updateCategory({ id, ...payload }) {
  const { data } = await fetchClient.put(`/catalog/categories/${id}`, payload);
  return data;
}

export async function deleteCategory(id) {
  await fetchClient.delete(`/catalog/categories/${id}`);
}

export async function listBrands(params) {
  const { data } = await fetchClient.get(`/catalog/brands${buildQueryString(params)}`);
  return data;
}

export async function createBrand(payload) {
  const { data } = await fetchClient.post('/catalog/brands', payload);
  return data;
}

export async function updateBrand({ id, ...payload }) {
  const { data } = await fetchClient.put(`/catalog/brands/${id}`, payload);
  return data;
}

export async function deleteBrand(id) {
  await fetchClient.delete(`/catalog/brands/${id}`);
}

export async function listModels(params) {
  const { data } = await fetchClient.get(`/catalog/models${buildQueryString(params)}`);
  return data;
}

export async function createModel(payload) {
  const { data } = await fetchClient.post('/catalog/models', payload);
  return data;
}

export async function updateModel({ id, ...payload }) {
  const { data } = await fetchClient.put(`/catalog/models/${id}`, payload);
  return data;
}

export async function deleteModel(id) {
  await fetchClient.delete(`/catalog/models/${id}`);
}

export async function listItems(params) {
  const { data } = await fetchClient.get(`/catalog/items${buildQueryString(params)}`);
  return data;
}

export async function createItem(payload) {
  const { data } = await fetchClient.post('/catalog/items', payload);
  return data;
}

export async function updateItem({ id, ...payload }) {
  const { data } = await fetchClient.put(`/catalog/items/${id}`, payload);
  return data;
}

export async function deleteItem(id) {
  await fetchClient.delete(`/catalog/items/${id}`);
}
