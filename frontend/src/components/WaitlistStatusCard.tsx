import { useEffect, useState } from 'react';
import { Clock3, ListOrdered, LogOut, Zap } from 'lucide-react';
import type { WaitlistStatus } from '../types';
import { formatDateTime } from '../lib/format';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface WaitlistStatusCardProps {
  status: WaitlistStatus;
  stationName?: string;
  onConfirm: () => void;
  onLeave: () => void;
  isConfirming?: boolean;
  isLeaving?: boolean;
}

function useCountdown(deadline?: string | null) {
  const [secondsLeft, setSecondsLeft] = useState(() => (deadline ? Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000)) : 0));

  useEffect(() => {
    if (!deadline) return;
    const tick = () => setSecondsLeft(Math.max(0, Math.round((new Date(deadline).getTime() - Date.now()) / 1000)));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [deadline]);

  return secondsLeft;
}

export function WaitlistStatusCard({ status, stationName, onConfirm, onLeave, isConfirming = false, isLeaving = false }: WaitlistStatusCardProps) {
  const hasOffer = Boolean(status.offered_port_id && status.offer_expires_at);
  const secondsLeft = useCountdown(status.offer_expires_at);
  const offerExpired = hasOffer && secondsLeft <= 0;

  return (
    <section className={`surface overflow-hidden border-2 ${hasOffer && !offerExpired ? 'border-[var(--amber)]' : 'border-transparent'}`}>
      <div className="flex flex-col gap-4 p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <Badge tone={hasOffer && !offerExpired ? 'warning' : 'info'}>{hasOffer && !offerExpired ? 'Port offered' : 'Waiting in queue'}</Badge>
              {stationName && <span className="text-sm font-bold text-[var(--steel-dark)]">{stationName}</span>}
            </div>
            {hasOffer && !offerExpired ? (
              <h3 className="font-display text-xl font-bold">Confirm within {secondsLeft}s or lose your spot</h3>
            ) : (
              <h3 className="font-display text-xl font-bold flex items-center gap-2"><ListOrdered size={20} className="text-[var(--teal)]" /> Position {status.position} in queue</h3>
            )}
            <p className="mt-1 text-sm text-[var(--steel)]">Joined {formatDateTime(status.joined_at)}</p>
          </div>
          <div className="flex gap-2">
            {hasOffer && !offerExpired && (
              <Button variant="primary" icon={<Zap size={16} />} onClick={onConfirm} isLoading={isConfirming}>Confirm reservation</Button>
            )}
            <Button variant="danger" icon={<LogOut size={16} />} onClick={onLeave} isLoading={isLeaving}>Leave waitlist</Button>
          </div>
        </div>
        {hasOffer && !offerExpired && (
          <p className="flex items-center gap-1.5 text-sm font-semibold text-[#78560b]"><Clock3 size={16} /> A port is being held for you. Confirm now to place a standard reservation and lock in your escrow.</p>
        )}
        {offerExpired && (
          <p className="text-sm text-[var(--steel)]">Your offer window has closed. The port is being reassigned; refresh shortly for your updated position.</p>
        )}
      </div>
    </section>
  );
}
