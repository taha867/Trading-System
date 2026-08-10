import toast from 'react-hot-toast';
import { HTTP_STATUS, TOAST_MESSAGES } from '@/utils/constants';
import { getToken, getRefreshToken, storeToken, removeTokens } from '@/utils/tokenUtils';

const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const TIMEOUT_MS = 15000;
const NO_AUTH_PATHS = ['/auth/login', '/auth/refresh'];

export class FetchError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'FetchError';
    this.status = status;
    this.data = data;
  }
}

let refreshPromise = null;

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  if (!refreshPromise) {
    refreshPromise = fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error('refresh failed');
        const data = await response.json();
        storeToken(data);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

function handleAuthFailure() {
  removeTokens();
  if (window.location.pathname !== '/sign-in') {
    window.location.href = '/sign-in';
  }
}

async function parseBody(response) {
  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function request(path, { method = 'GET', body, headers = {}, skipAuth = false, isRetry = false } = {}) {
  const url = `${BASE_URL}${path}`;
  const authHeaders = skipAuth || NO_AUTH_PATHS.includes(path) ? {} : buildAuthHeaders();

  let response;
  try {
    response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json', ...authHeaders, ...headers },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    toast.error(TOAST_MESSAGES.NETWORK_ERROR);
    throw new FetchError(TOAST_MESSAGES.NETWORK_ERROR, 0);
  }

  if (response.status === HTTP_STATUS.UNAUTHORIZED && !skipAuth && !isRetry && !NO_AUTH_PATHS.includes(path)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return request(path, { method, body, headers, skipAuth, isRetry: true });
    }
    handleAuthFailure();
    throw new FetchError(TOAST_MESSAGES.SESSION_EXPIRED, response.status);
  }

  const data = await parseBody(response);

  if (!response.ok) {
    // data.detail is usually a plain string (HTTPException(detail="...")), but a
    // raw FastAPI/Pydantic 422 sends an array of {type, loc, msg, input} objects
    // instead — passing that straight to toast.error() renders objects as React
    // children and crashes the whole app. Reduce it to a readable string first.
    const rawDetail = data?.detail;
    const detail = Array.isArray(rawDetail)
      ? rawDetail.map((item) => item?.msg ?? String(item)).join('; ') || TOAST_MESSAGES.GENERIC_ERROR
      : rawDetail || TOAST_MESSAGES.GENERIC_ERROR;
    toast.error(detail);
    throw new FetchError(detail, response.status, data);
  }

  return { data, status: response.status, ok: true, headers: response.headers };
}

function buildAuthHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const fetchClient = {
  get: (path, opts) => request(path, { ...opts, method: 'GET' }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  delete: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
};
