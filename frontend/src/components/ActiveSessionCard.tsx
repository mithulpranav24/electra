import { BatteryCharging, Clock3, Timer, Zap } from 'lucide-react';
import type { ChargingSessionStatus } from '../types';
import { formatCurrency } from '../lib/format';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface ActiveSessionCardProps {
  status: ChargingSessionStatus;
  onStop: () => void;
  isStopping?: boolean;
}

function formatMinutes(minutes: number) {
  if (minutes <= 0) return 'now';
  if (minutes < 60) return `${Math.ceil(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const remaining = Math.ceil(minutes % 60);
  return `${hours}h ${remaining}m`;
}

export function ActiveSessionCard({ status, onStop, isStopping = false }: ActiveSessionCardProps) {
  const progressPercent = Math.min(100, Math.max(0, ((status.current_battery_percentage - status.initial_battery_percentage) / (status.target_battery_percentage - status.initial_battery_percentage || 1)) * 100));
  // target_reached alone means "plugged in, energy has stopped flowing" - that's
  // true throughout the 30-minute grace period too, before idle_minutes (billable
  // idle time) starts accruing. Keeping these separate means the badge correctly
  // switches away from "Charging" as soon as the target is hit, while the fee
  // warning only appears once fees are actually accruing.
  const isPluggedInIdle = status.target_reached;
  const isAccruingFees = status.idle_minutes > 0;

  return (
    <section className="overflow-hidden rounded-[var(--radius-lg)] bg-[var(--night)] text-white shadow-[var(--shadow-md)]">
      <div className="flex flex-col gap-5 p-5 sm:p-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Badge tone={isPluggedInIdle ? 'warning' : 'success'}>{isPluggedInIdle ? 'Idle — plugged in' : 'Charging'}</Badge>
            {isAccruingFees && <span className="text-xs font-semibold text-white/60">Idle fees are accruing</span>}
          </div>
          <Button variant="danger" onClick={onStop} isLoading={isStopping}>Stop charging</Button>
        </div>

        <div>
          <div className="flex items-end justify-between">
            <h3 className="font-display text-4xl font-bold tracking-tight">{Number(status.current_battery_percentage).toFixed(1)}%</h3>
            <span className="pb-1 text-sm font-semibold text-white/60">Target {Number(status.target_battery_percentage).toFixed(0)}%</span>
          </div>
          <div className="mt-3 h-2.5 w-full overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full bg-[var(--amber)] transition-[width]" style={{ width: `${progressPercent}%` }} />
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-lg bg-white/5 p-3.5">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-white/45"><Zap size={14} /> Energy</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">{Number(status.energy_delivered_kwh).toFixed(2)} kWh</dd>
          </div>
          <div className="rounded-lg bg-white/5 p-3.5">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-white/45"><Timer size={14} /> {status.target_reached ? 'Idle time' : 'ETA'}</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">{status.target_reached ? formatMinutes(status.idle_minutes) : formatMinutes(status.eta_minutes_remaining)}</dd>
          </div>
          <div className="rounded-lg bg-white/5 p-3.5">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-white/45"><BatteryCharging size={14} /> Idle fee</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">{formatCurrency(status.idle_fee)}</dd>
          </div>
          <div className="rounded-lg bg-[var(--amber)] p-3.5 text-[var(--night)]">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em]"><Clock3 size={14} /> Cost so far</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">{formatCurrency(status.total_cost)}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
