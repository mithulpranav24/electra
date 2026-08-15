import { createContext, useContext } from 'react';

export type ToastTone = 'success' | 'error' | 'info';
export interface ToastInput { title: string; message?: string; tone?: ToastTone; }
export interface ToastContextValue { pushToast: (toast: ToastInput) => void; }

export const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
}
