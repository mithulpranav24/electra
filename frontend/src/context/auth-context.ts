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
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
}
