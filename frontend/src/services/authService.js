import { fetchClient } from '@/middleware/fetchClient';

export async function signIn({ username, password }) {
  const { data } = await fetchClient.post('/auth/login', { username, password }, { skipAuth: true });
  return data; // { access_token, refresh_token, token_type }
}

export async function refreshToken(refresh_token) {
  const { data } = await fetchClient.post('/auth/refresh', { refresh_token }, { skipAuth: true });
  return data; // { access_token, refresh_token, token_type }
}

export async function fetchCurrentUser() {
  const { data } = await fetchClient.get('/auth/me');
  return data; // { id, username, is_active }
}
