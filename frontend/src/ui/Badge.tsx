import type { ReactNode } from 'react';

import type { StatusTone } from '../lib/status';

const tones: Record<StatusTone, string> = {
  neutral: 'bg-[var(--paper-muted)] text-[var(--steel-dark)] border-[var(--line)]',
  success: 'bg-[var(--teal-soft)] text-[var(--teal-dark)] border-[var(--teal)]/20',
  warning: 'bg-[var(--amber-soft)] text-[#75530b] border-[var(--amber)]/30',
  danger: 'bg-[var(--red-soft)] text-[var(--red-dark)] border-[var(--red)]/20',
  info: 'bg-[var(--blue-soft)] text-[#285270] border-[var(--blue)]/20',
};

export function Badge({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: StatusTone; className?: string }) {
  return <span className={`inline-flex min-h-6 items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${tones[tone]} ${className}`}>{children}</span>;
}
