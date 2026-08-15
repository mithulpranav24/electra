import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';
import { ToastContext, type ToastInput, type ToastTone } from './ToastContext';

interface ToastItem extends ToastInput { id: number; tone: ToastTone; }
let nextToastId = 1;

const iconByTone = { success: CheckCircle2, error: AlertCircle, info: Info };
const styleByTone = {
  success: 'border-[var(--teal)]/30 text-[var(--teal-dark)]',
  error: 'border-[var(--red)]/30 text-[var(--red-dark)]',
  info: 'border-[var(--blue)]/30 text-[#285270]',
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const removeToast = useCallback((id: number) => setToasts((items) => items.filter((item) => item.id !== id)), []);
  const pushToast = useCallback((toast: ToastInput) => {
    const id = nextToastId++;
    setToasts((items) => [...items.slice(-2), { ...toast, id, tone: toast.tone ?? 'info' }]);
    window.setTimeout(() => removeToast(id), 5000);
  }, [removeToast]);
  const value = useMemo(() => ({ pushToast }), [pushToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed inset-x-3 top-3 z-[100] flex flex-col items-end gap-2 sm:inset-x-auto sm:right-5 sm:top-5 sm:w-[24rem]" aria-live="polite" aria-atomic="false">
        {toasts.map((toast) => {
          const Icon = iconByTone[toast.tone];
          return (
            <div key={toast.id} className={`pointer-events-auto enter-up flex w-full gap-3 rounded-[var(--radius-md)] border bg-white p-4 shadow-[var(--shadow-md)] ${styleByTone[toast.tone]}`} role={toast.tone === 'error' ? 'alert' : 'status'}>
              <Icon size={20} className="mt-0.5 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-bold">{toast.title}</p>
                {toast.message && <p className="mt-0.5 text-sm text-[var(--steel-dark)]">{toast.message}</p>}
              </div>
              <button type="button" className="-mr-1 -mt-1 flex size-8 items-center justify-center rounded-full hover:bg-black/5" onClick={() => removeToast(toast.id)} aria-label="Dismiss notification"><X size={16} /></button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
