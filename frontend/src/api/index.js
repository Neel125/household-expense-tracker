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
  referrals: {
    // The household's code, who it has brought in, and how close each of
    // them is to earning both sides a payout.
    summary: () => http.get('/api/referrals'),
    // Public: lets the sign-up screen name who invited you.
    preview: (code) => http.get(`/api/referrals/preview/${encodeURIComponent(code)}`),
  },
  rewards: {
    // One GET backs the whole Rewards page; reading it also settles
    // anything earned since the last look (see RewardsService.settle).
    summary: () => http.get('/api/rewards'),
    health: (month) => http.get('/api/rewards/health' + (month ? `?month=${encodeURIComponent(month)}` : '')),
    recordReview: (month) => http.post('/api/rewards/review', { month }),
    joinChallenge: (key) => http.post(`/api/rewards/challenges/${encodeURIComponent(key)}/join`),
    leaveChallenge: (key) => http.del(`/api/rewards/challenges/${encodeURIComponent(key)}`),
    quiz: () => http.get('/api/rewards/games/quiz'),
    submitQuiz: (data) => http.post('/api/rewards/games/quiz', data),
    puzzle: () => http.get('/api/rewards/games/puzzle'),
    submitPuzzle: (data) => http.post('/api/rewards/games/puzzle', data),
    wheel: () => http.get('/api/rewards/games/wheel'),
    spin: () => http.post('/api/rewards/games/spin'),
  },
  goals: {
    list: () => http.get('/api/goals'),
    create: (data) => http.post('/api/goals', data),
    update: (id, data) => http.put(`/api/goals/${id}`, data),
    contribute: (id, amount) => http.post(`/api/goals/${id}/contribute`, { amount }),
    remove: (id) => http.del(`/api/goals/${id}`),
  },
  investments: {
    list: () => http.get('/api/investments'),
    // The holding plus every linked contribution — fetched on demand by
    // the Portfolio page's detail modal, not on every page load.
    get: (id) => http.get(`/api/investments/${id}`),
    create: (data) => http.post('/api/investments', data),
    update: (id, data) => http.put(`/api/investments/${id}`, data),
    remove: (id) => http.del(`/api/investments/${id}`),
  },
  debts: {
    list: () => http.get('/api/debts'),
    // The interest/principal split of every EMI logged against a loan.
    schedule: (id) => http.get(`/api/debts/${id}/schedule`),
    create: (data) => http.post('/api/debts', data),
    update: (id, data) => http.put(`/api/debts/${id}`, data),
    remove: (id) => http.del(`/api/debts/${id}`),
  },
};
