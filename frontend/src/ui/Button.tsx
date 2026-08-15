import type { ButtonHTMLAttributes, ReactNode } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  icon?: ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary: 'border-[var(--teal)] bg-[var(--teal)] text-white hover:border-[var(--teal-dark)] hover:bg-[var(--teal-dark)] shadow-sm',
  secondary: 'border-[var(--line-strong)] bg-white text-[var(--ink)] hover:border-[var(--teal)] hover:text-[var(--teal-dark)] shadow-sm',
  ghost: 'border-transparent bg-transparent text-[var(--steel-dark)] hover:bg-[var(--paper-muted)] hover:text-[var(--ink)]',
  danger: 'border-[var(--red)] bg-[var(--red)] text-white hover:border-[var(--red-dark)] hover:bg-[var(--red-dark)] shadow-sm',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'min-h-9 px-3 text-sm',
  md: 'min-h-11 px-4 text-sm',
  lg: 'min-h-12 px-5 text-base',
};

export function Button({ variant = 'secondary', size = 'md', isLoading = false, icon, className = '', disabled, children, type = 'button', ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex shrink-0 items-center justify-center gap-2 rounded-[var(--radius-sm)] border font-bold transition active:translate-y-px disabled:cursor-not-allowed disabled:opacity-55 ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || isLoading}
      aria-busy={isLoading || undefined}
      {...props}
    >
      {isLoading ? <span className="spinner" aria-hidden="true" /> : icon}
      <span>{children}</span>
    </button>
  );
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
  variant?: 'default' | 'danger';
}

export function IconButton({ label, children, className = '', variant = 'default', type = 'button', ...props }: IconButtonProps) {
  return (
    <button
      type={type}
      className={`inline-flex size-11 shrink-0 items-center justify-center rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50 ${variant === 'danger' ? 'border-[var(--red-soft)] bg-[var(--red-soft)] text-[var(--red)] hover:border-[var(--red)]' : 'border-[var(--line)] bg-white text-[var(--steel-dark)] hover:border-[var(--teal)] hover:text-[var(--teal)]'} ${className}`}
      aria-label={label}
      title={label}
      {...props}
    >
      {children}
    </button>
  );
}
