import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api } from '../api';
import { getToken, onUnauthorized, setToken } from '../api/client';

const AuthContext = createContext(null);

// Holds the signed-in identity (user + household) and the auth actions.
// The rest of the app reads `user` to know it's authenticated; a missing
// user means the router shows the login/register screens.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [household, setHousehold] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyAuth = useCallback((data) => {
    setToken(data.token);
    setUser(data.user);
    setHousehold(data.household);
  }, []);

  const logout = useCallback(() => {
    setToken('');
    setUser(null);
    setHousehold(null);
  }, []);

  // A 401 anywhere (expired/invalid token) drops us back to login.
  useEffect(() => onUnauthorized(() => logout()), [logout]);

  // Restore the session on load if a token is present.
  useEffect(() => {
    let alive = true;
    (async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const data = await api.auth.me();
        if (alive) {
          setUser(data.user);
          setHousehold(data.household);
        }
      } catch {
        if (alive) logout();
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [logout]);

  const login = useCallback(async (email, password) => {
    applyAuth(await api.auth.login({ email, password }));
  }, [applyAuth]);

  const register = useCallback(async (payload) => {
    applyAuth(await api.auth.register(payload));
  }, [applyAuth]);

  const acceptInvite = useCallback(async (payload) => {
    applyAuth(await api.auth.acceptInvite(payload));
  }, [applyAuth]);

  // Update the signed-in user's profile. Returns the fresh user so callers
  // can react to the saved values.
  const updateProfile = useCallback(async (payload) => {
    const data = await api.auth.updateProfile(payload);
    setUser(data.user);
    setHousehold(data.household);
    return data.user;
  }, []);

  const value = {
    user,
    household,
    setHousehold,
    loading,
    isOwner: user?.role === 'owner',
    login,
    register,
    acceptInvite,
    updateProfile,
    logout,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
