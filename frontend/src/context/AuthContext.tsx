import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { User } from '../types';
import { authService } from '../services/api';

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

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
  }), [fetchUser, isLoading, login, logout, token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
