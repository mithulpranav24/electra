import type { ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Inbox, RefreshCw } from 'lucide-react';
import { Button } from './Button';

interface AlertProps {
  tone?: 'error' | 'success' | 'info' | 'warning';
  title?: string;
  children: ReactNode;
  className?: string;
  role?: 'alert' | 'status';
}

const alertStyles = {
  error: 'border-[var(--red)]/25 bg-[var(--red-soft)] text-[var(--red-dark)]',
  success: 'border-[var(--teal)]/25 bg-[var(--teal-soft)] text-[var(--teal-dark)]',
  info: 'border-[var(--blue)]/25 bg-[var(--blue-soft)] text-[#274f70]',
  warning: 'border-[var(--amber)]/40 bg-[var(--amber-soft)] text-[#73530d]',
};

export function Alert({ tone = 'info', title, children, className = '', role }: AlertProps) {
  const Icon = tone === 'success' ? CheckCircle2 : AlertCircle;
  return (
    <div className={`flex gap-3 rounded-[var(--radius-md)] border p-4 text-sm ${alertStyles[tone]} ${className}`} role={role ?? (tone === 'error' ? 'alert' : 'status')}>
      <Icon size={19} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        {title && <p className="mb-0.5 font-bold">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  );
}

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}

export function EmptyState({ title, description, icon, action, compact = false }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? 'px-4 py-8' : 'min-h-64 px-6 py-12'}`}>
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-[var(--paper-muted)] text-[var(--steel)]">
        {icon ?? <Inbox size={23} aria-hidden="true" />}
      </div>
      <h3 className="font-display text-lg font-bold text-[var(--ink)]">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-[var(--steel)]">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function LoadingState({ label = 'Loading', compact = false }: { label?: string; compact?: boolean }) {
  return (
    <div className={`flex items-center justify-center gap-3 text-sm font-semibold text-[var(--steel)] ${compact ? 'p-5' : 'min-h-64 p-8'}`} role="status">
      <span className="spinner text-[var(--teal)]" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ title = 'Something went wrong', description, onRetry }: { title?: string; description: string; onRetry?: () => void }) {
  return (
    <div className="surface flex min-h-56 flex-col items-center justify-center px-6 py-10 text-center" role="alert">
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-[var(--red-soft)] text-[var(--red)]">
        <AlertCircle size={24} aria-hidden="true" />
      </div>
      <h3 className="font-display text-lg font-bold">{title}</h3>
      <p className="mt-1 max-w-lg text-sm text-[var(--steel)]">{description}</p>
      {onRetry && <Button className="mt-5" icon={<RefreshCw size={17} />} onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-[#dfe6e1] ${className}`} aria-hidden="true" />;
}
