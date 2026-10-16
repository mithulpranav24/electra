import { createContext, useContext } from 'react';
import type { User } from '../types';

export interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  user: User | null;
  isLoading: boolean;
  login: (token: string) => void;
  logout: () => Promise<void>;
  fetchUser: () => Promise<void>;
  /** Silently re-fetch the signed-in user (e.g. after a wallet balance change)
   *  without toggling the global loading state or signing out on failure. */
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
