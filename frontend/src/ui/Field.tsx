import { useId, type ReactNode } from 'react';

interface FieldProps {
  label: string;
  children: (props: { id: string; describedBy?: string; invalid?: boolean }) => ReactNode;
  hint?: string;
  error?: string;
  optional?: boolean;
  className?: string;
}

export function Field({ label, children, hint, error, optional = false, className = '' }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className}`}>
      <label htmlFor={id} className="field-label">
        {label}
        {optional && <span className="font-normal text-[var(--steel)]">(optional)</span>}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint && <p id={hintId} className="m-0 text-xs text-[var(--steel)]">{hint}</p>}
      {error && <p id={errorId} className="m-0 text-xs font-semibold text-[var(--red)]">{error}</p>}
    </div>
  );
}
