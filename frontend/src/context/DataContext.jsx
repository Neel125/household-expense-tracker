import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { useAuth } from './AuthContext';
import { useToast } from './ToastContext';

const DataContext = createContext(null);

const EMPTY = {
  transactions: [],
  members: [],
  accounts: [],
  categories: [],
  incomeSources: [],
  goals: [],
  budget: { monthlyBudget: 0, categories: [] },
  rewards: null,
};

// Loads and caches every household collection once the user is signed in,
// and exposes mutation helpers that re-read what they changed (same
// load-then-refresh pattern the app has always used). Toasts are raised
// here so pages don't each reimplement error handling.
export function DataProvider({ children }) {
  const { user } = useAuth();
  const toast = useToast();
  const [data, setData] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState('household'); // household | mine

  const refresh = useCallback(async () => {
    try {
      const [transactions, members, accounts, categories, incomeSources, goals, budget, rewards] = await Promise.all([
        api.transactions.list(),
        api.members.list(),
        api.accounts.list(),
        api.categories.list(),
        api.income.list(),
        api.goals.list(),
        api.budget.get(),
        // Coins move whenever transactions or goals do, so rewards ride
        // along on the same refresh instead of the page polling. Rewards
        // are a bonus layer, not the books: if that one call fails the
        // rest of the app must still load, so it resolves to null instead
        // of rejecting the whole batch.
        api.rewards.summary().catch((e) => {
          console.error('Rewards unavailable', e);
          return null;
        }),
      ]);
      setData({ transactions, members, accounts, categories, incomeSources, goals, budget, rewards });
    } catch (e) {
      console.error('Failed to load data', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      setLoading(true);
      refresh();
    } else {
      setData(EMPTY);
    }
  }, [user, refresh]);

  // The member name the signed-in user logs as — drives the "Just me" scope.
  const profile = useMemo(() => {
    const m = data.members.find((mm) => mm.id === user?.memberId);
    return m ? m.name : user?.displayName || '';
  }, [data.members, user]);

  // Generic wrapper: run a mutation, refresh, toast success or failure.
  const run = useCallback(
    async (fn, successMsg) => {
      try {
        const result = await fn();
        await refresh();
        if (successMsg) toast(successMsg);
        return result ?? true;
      } catch (e) {
        toast(e.message);
        return false;
      }
    },
    [refresh, toast]
  );

  const actions = useMemo(
    () => ({
      // transactions
      saveTransaction: (id, payload) =>
        run(
          () => (id ? api.transactions.update(id, payload) : api.transactions.create(payload)),
          id ? 'Transaction updated' : 'Transaction saved'
        ),
      deleteTransaction: (id) => run(() => api.transactions.remove(id), 'Transaction deleted'),

      // members
      addMember: (payload) => run(() => api.members.create(payload), `${payload.name} added`),
      updateMember: (id, payload) => run(() => api.members.update(id, payload), `${payload.name} updated`),
      removeMember: (id, reassignTo) => run(() => api.members.remove(id, reassignTo), 'Member removed'),

      // accounts
      addAccount: (payload) => run(() => api.accounts.create(payload), `${payload.name} added`),
      updateAccount: (id, payload) => run(() => api.accounts.update(id, payload), 'Account updated'),
      removeAccount: (id) => run(() => api.accounts.remove(id), 'Account removed'),

      // categories
      addCategory: (payload) => run(() => api.categories.create(payload), `${payload.name} added`),
      updateCategory: (id, payload) => run(() => api.categories.update(id, payload), 'Category updated'),
      removeCategory: (id) => run(() => api.categories.remove(id), 'Category removed'),

      // budget
      saveBudget: (payload) => run(() => api.budget.update(payload), 'Budget saved'),

      // income
      addIncome: (payload) => run(() => api.income.create(payload), `${payload.name} added`),
      updateIncome: (id, payload) => run(() => api.income.update(id, payload), 'Income source updated'),
      removeIncome: (id) => run(() => api.income.remove(id), 'Income source removed'),

      // rewards
      joinChallenge: (key, title) => run(() => api.rewards.joinChallenge(key), `Joined “${title}”`),
      leaveChallenge: (key) => run(() => api.rewards.leaveChallenge(key), 'Left the challenge'),
      recordReview: (month) => run(() => api.rewards.recordReview(month), 'Review logged — coins added'),

      // goals
      addGoal: (payload) => run(() => api.goals.create(payload), `${payload.name} created`),
      updateGoal: (id, payload) => run(() => api.goals.update(id, payload), 'Goal updated'),
      contributeGoal: (id, amount) => run(() => api.goals.contribute(id, amount), 'Contribution added'),
      removeGoal: (id) => run(() => api.goals.remove(id), 'Goal removed'),
    }),
    [run]
  );

  const value = { ...data, loading, scope, setScope, profile, refresh, ...actions };
  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error('useData must be used within DataProvider');
  return ctx;
}
