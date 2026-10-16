import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { User } from '../types';
import { authService } from '../services/api';
import { AuthContext, type AuthContextType } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      setIsLoading(true);
      setUser(await authService.getCurrentUser());
    } catch (error) {
      console.error('Failed to restore the signed-in user', error);
      localStorage.removeItem('token');
      setToken(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      void fetchUser();
    } else {
      localStorage.removeItem('token');
      setUser(null);
      setIsLoading(false);
    }
  }, [fetchUser, token]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setToken(null);
      setUser(null);
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key === 'token') setToken(event.newValue);
    };
    window.addEventListener('auth-unauthorized', handleUnauthorized);
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener('auth-unauthorized', handleUnauthorized);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await authService.getCurrentUser());
    } catch (error) {
      // A transient refresh failure must not flip the global loader or sign the
      // user out — the displayed balance just stays until the next refresh.
      console.error('Failed to refresh the signed-in user', error);
    }
  }, []);

  const login = useCallback((newToken: string) => {
    setIsLoading(true);
    setToken(newToken);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (token) await authService.logout();
    } catch (error) {
      console.error('Backend logout failed; local session was still cleared', error);
    } finally {
      setToken(null);
      setUser(null);
    }
  }, [token]);

  const value = useMemo<AuthContextType>(() => ({
    token,
    isAuthenticated: Boolean(token && user),
    user,
    isLoading,
    login,
    logout,
    fetchUser,
    refreshUser,
  }), [fetchUser, isLoading, login, logout, refreshUser, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
