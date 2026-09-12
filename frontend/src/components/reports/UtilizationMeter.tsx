export function UtilizationMeter({ percent }: { percent: number }) {
  const clamped = Math.min(100, Math.max(0, percent));
  const severity = clamped >= 85 ? 'var(--amber)' : 'var(--teal)';

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="font-data text-3xl font-bold">{clamped.toFixed(1)}%</span>
        <span className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Occupied now</span>
      </div>
      <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-[var(--teal-soft)]">
        <div className="h-full rounded-full transition-[width]" style={{ width: `${clamped}%`, background: severity }} />
      </div>
    </div>
  );
}
