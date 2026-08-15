import type { ReactNode } from 'react';

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-extrabold uppercase tracking-[0.16em] text-[var(--teal)]">{eyebrow}</p>}
        <h1 className="font-display text-3xl font-bold tracking-[-0.025em] text-[var(--ink)] sm:text-[2.1rem]">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-[var(--steel)] sm:text-base">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </header>
  );
}

interface SectionHeaderProps { title: string; description?: string; action?: ReactNode; }

export function SectionHeader({ title, description, action }: SectionHeaderProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h2 className="font-display text-lg font-bold tracking-tight">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-[var(--steel)]">{description}</p>}
      </div>
      {action}
    </div>
  );
}
