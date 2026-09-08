import { http } from './client';

// One object per resource, grouping the endpoints. Keeps callers
// (contexts) decoupled from URL strings and HTTP verbs.
export const api = {
  auth: {
    register: (data) => http.post('/api/auth/register', data),
    login: (data) => http.post('/api/auth/login', data),
    me: () => http.get('/api/auth/me'),
    updateProfile: (data) => http.patch('/api/auth/me', data),
    listInvites: () => http.get('/api/auth/invites'),
    createInvite: (data) => http.post('/api/auth/invites', data),
    previewInvite: (token) => http.get(`/api/auth/invites/${encodeURIComponent(token)}/preview`),
    acceptInvite: (data) => http.post('/api/auth/accept-invite', data),
  },
  transactions: {
    list: () => http.get('/api/transactions'),
    create: (data) => http.post('/api/transactions', data),
    update: (id, data) => http.put(`/api/transactions/${id}`, data),
    remove: (id) => http.del(`/api/transactions/${id}`),
  },
  members: {
    list: () => http.get('/api/members'),
    create: (data) => http.post('/api/members', data),
    update: (id, data) => http.put(`/api/members/${id}`, data),
    remove: (id, reassignTo) =>
      http.del(`/api/members/${id}` + (reassignTo === undefined ? '' : `?reassign_to=${encodeURIComponent(reassignTo)}`)),
  },
  accounts: {
    list: () => http.get('/api/accounts'),
    create: (data) => http.post('/api/accounts', data),
    update: (id, data) => http.put(`/api/accounts/${id}`, data),
    remove: (id) => http.del(`/api/accounts/${id}`),
  },
  categories: {
    list: () => http.get('/api/categories'),
    create: (data) => http.post('/api/categories', data),
    update: (id, data) => http.put(`/api/categories/${id}`, data),
    remove: (id) => http.del(`/api/categories/${id}`),
  },
  budget: {
    get: () => http.get('/api/budget'),
    update: (data) => http.put('/api/budget', data),
  },
  income: {
    list: () => http.get('/api/income-sources'),
    create: (data) => http.post('/api/income-sources', data),
    update: (id, data) => http.put(`/api/income-sources/${id}`, data),
    remove: (id) => http.del(`/api/income-sources/${id}`),
  },
  goals: {
    list: () => http.get('/api/goals'),
    create: (data) => http.post('/api/goals', data),
    update: (id, data) => http.put(`/api/goals/${id}`, data),
    contribute: (id, amount) => http.post(`/api/goals/${id}/contribute`, { amount }),
    remove: (id) => http.del(`/api/goals/${id}`),
  },
};
