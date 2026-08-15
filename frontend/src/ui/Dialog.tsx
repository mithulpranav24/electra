import { useEffect, useId, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { IconButton } from './Button';

interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  preventClose?: boolean;
}

const sizes = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl', xl: 'max-w-5xl' };

export function Dialog({ open, onClose, title, description, children, footer, size = 'md', preventClose = false }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`m-auto max-h-[calc(100vh-2rem)] w-[calc(100%-2rem)] overflow-hidden rounded-[var(--radius-lg)] border-0 bg-white p-0 text-[var(--ink)] shadow-[var(--shadow-lg)] ${sizes[size]}`}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => { event.preventDefault(); if (!preventClose) onClose(); }}
      onClick={(event) => { if (!preventClose && event.target === ref.current) onClose(); }}
    >
      <div className="flex max-h-[calc(100vh-2rem)] flex-col">
        <header className="flex items-start justify-between gap-4 border-b border-[var(--line)] px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <h2 id={titleId} className="font-display text-xl font-bold tracking-tight">{title}</h2>
            {description && <p id={descriptionId} className="mt-1 text-sm text-[var(--steel)]">{description}</p>}
          </div>
          <IconButton label={`Close ${title}`} onClick={onClose} disabled={preventClose} className="-mr-1 -mt-1"><X size={19} /></IconButton>
        </header>
        <div className="app-scrollbar overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
        {footer && <footer className="flex flex-wrap justify-end gap-3 border-t border-[var(--line)] bg-[#fafbfa] px-5 py-4 sm:px-6">{footer}</footer>}
      </div>
    </dialog>
  );
}
