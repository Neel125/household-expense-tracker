// Thin fetch wrapper around the FastAPI backend. In dev, Vite proxies
// /api to http://127.0.0.1:8000 (see vite.config.js); in production the
// backend serves this app itself, so /api is already same-origin.
//
// The JWT lives in localStorage and is attached to every request. A 401
// clears it and notifies listeners (AuthContext) so the app returns to
// the login screen.
const BASE = import.meta.env.VITE_API_URL || '';
const TOKEN_KEY = 'lc_token';

const listeners = new Set();

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function onUnauthorized(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export async function request(path, opts = {}) {
  const token = getToken();
  const res = await fetch(BASE + path, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...opts,
  });

  if (res.status === 401) {
    setToken('');
    listeners.forEach((fn) => fn());
  }

  if (!res.ok) {
    // FastAPI puts the readable reason in `detail` (a string, or a list of
    // field errors for 422s) — surface that so callers can toast it as-is.
    const body = await res.json().catch(() => null);
    const detail = body && body.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d) => d.msg).filter(Boolean).join('; ')
      : typeof detail === 'string'
        ? detail
        : '';
    throw new Error(msg || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const http = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body ?? {}) }),
  put: (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  del: (path) => request(path, { method: 'DELETE' }),
};
