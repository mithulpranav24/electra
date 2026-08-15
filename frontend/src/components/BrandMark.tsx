import { Zap } from 'lucide-react';

export function BrandMark({ compact = false, inverse = false }: { compact?: boolean; inverse?: boolean }) {
  return (
    <div className="inline-flex items-center gap-3" aria-label="Electra">
      <span className={`relative flex size-10 items-center justify-center rounded-[0.75rem] ${inverse ? 'bg-[var(--amber)] text-[var(--night)]' : 'bg-[var(--night)] text-[var(--amber)]'}`} aria-hidden="true">
        <Zap size={21} strokeWidth={2.6} />
        <span className={`absolute -bottom-1 left-1/2 h-2 w-px -translate-x-1/2 ${inverse ? 'bg-[var(--amber)]' : 'bg-[var(--night)]'}`} />
      </span>
      {!compact && (
        <span className="font-display text-[1.45rem] font-bold leading-none tracking-[-0.04em]">
          Electra
        </span>
      )}
    </div>
  );
}
