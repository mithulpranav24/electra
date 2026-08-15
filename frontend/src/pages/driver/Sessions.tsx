import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarClock, Clock3, History, MapPinned, XCircle } from 'lucide-react';
import { reservationService } from '../../services/api';
import type { Reservation } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, formatDateTime, shortId } from '../../lib/format';
import { Badge, statusTone } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { ConfirmDialog } from '../../ui/ConfirmDialog';
import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

function arrivalLabel(expiresAt: string) {
  const milliseconds = new Date(expiresAt).getTime() - Date.now();
  if (milliseconds <= 0) return 'Expiry is being processed';
  const minutes = Math.max(1, Math.ceil(milliseconds / 60000));
  return `${minutes} minute${minutes === 1 ? '' : 's'} remaining`;
}

export function Sessions() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState<Reservation | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const { pushToast } = useToast();

  const loadReservations = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      setReservations(await reservationService.getActive());
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Active reservations could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void loadReservations(); }, [loadReservations]);

  const handleCancel = async () => {
    if (!cancelling) return;
    setIsCancelling(true);
    try {
      await reservationService.cancel(cancelling.reservation_id);
      setCancelling(null);
      await loadReservations();
      pushToast({ title: 'Reservation cancelled', message: 'Your wallet activity shows whether the escrow was refunded or forfeited.', tone: 'success' });
    } catch (cancelError) {
      pushToast({ title: 'Couldn’t cancel the reservation', message: getErrorMessage(cancelError, 'The reservation state may have changed.'), tone: 'error' });
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Activity" title="Reservations & charging" description="Time-sensitive reservations appear first, followed by your charging history when available." actions={<Link to="/driver/search"><Button variant="primary" icon={<MapPinned size={18} />}>Find charging</Button></Link>} />

      <section className="surface overflow-hidden">
        <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Active reservations" description="You can hold one active reservation across all vehicles." /></div>
        {isLoading ? <LoadingState label="Checking active reservations" /> : error ? <div className="p-4 sm:p-5"><ErrorState description={error} onRetry={() => void loadReservations()} /></div> : reservations.length === 0 ? (
          <EmptyState title="No active reservations" description="Search stations to compare available ports and reserve your next charge." icon={<CalendarClock size={23} />} action={<Link to="/driver/search"><Button variant="primary" icon={<MapPinned size={17} />}>Explore stations</Button></Link>} />
        ) : (
          <div className="divide-y divide-[var(--line)]">
            {reservations.map((reservation) => (
              <article key={reservation.reservation_id} className="p-5 sm:p-6">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                  <div className="min-w-0">
                    <div className="mb-3 flex flex-wrap items-center gap-2"><Badge tone={statusTone(reservation.status)}>{reservation.status}</Badge><span className="font-data text-xs text-[var(--steel)]">Reservation {shortId(reservation.reservation_id)}</span></div>
                    <h3 className="font-display text-xl font-bold">Arrive by {formatDateTime(reservation.expires_at)}</h3>
                    <p className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-[#78560b]"><Clock3 size={16} /> {arrivalLabel(reservation.expires_at)}</p>
                  </div>
                  <Button variant="danger" icon={<XCircle size={17} />} onClick={() => setCancelling(reservation)}>Cancel reservation</Button>
                </div>
                <dl className="mt-5 grid gap-3 sm:grid-cols-3">
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Port</dt><dd className="font-data mt-1 truncate font-bold" title={reservation.port_id}>{shortId(reservation.port_id, 12)}</dd></div>
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Vehicle</dt><dd className="font-data mt-1 truncate font-bold" title={reservation.vehicle_id}>{shortId(reservation.vehicle_id, 12)}</dd></div>
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Reserved tariff</dt><dd className="font-data mt-1 font-bold">{formatCurrency(reservation.reserved_tariff)}/kWh</dd></div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="surface overflow-hidden">
        <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Charging history" description="Completed sessions will include energy, cost, vehicle, and invoice details." /></div>
        <EmptyState title="No completed sessions available" description="The current backend does not yet expose charging-session history. This section is ready to display it when that API is connected." icon={<History size={23} />} />
      </section>

      <ConfirmDialog
        open={Boolean(cancelling)}
        onClose={() => setCancelling(null)}
        onConfirm={() => void handleCancel()}
        title="Cancel this reservation?"
        description="The backend decides whether the ₹1,000 escrow is refunded based on how long the port was held and your recent cancellation history. If the free-cancellation conditions are not met, the escrow is forfeited."
        confirmLabel="Cancel reservation"
        isLoading={isCancelling}
      />
    </div>
  );
}

export default Sessions;
