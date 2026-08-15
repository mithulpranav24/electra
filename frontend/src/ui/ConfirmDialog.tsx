import type { ReactNode } from 'react';
import { Button } from './Button';
import { Dialog } from './Dialog';

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  description: ReactNode;
  confirmLabel: string;
  isLoading?: boolean;
  tone?: 'danger' | 'primary';
}

export function ConfirmDialog({ open, onClose, onConfirm, title, description, confirmLabel, isLoading = false, tone = 'danger' }: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      preventClose={isLoading}
      footer={<><Button onClick={onClose} disabled={isLoading}>Cancel</Button><Button variant={tone === 'danger' ? 'danger' : 'primary'} onClick={onConfirm} isLoading={isLoading}>{confirmLabel}</Button></>}
    >
      <div className="text-sm leading-6 text-[var(--steel-dark)]">{description}</div>
    </Dialog>
  );
}
