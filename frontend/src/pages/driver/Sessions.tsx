import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BatteryCharging, CalendarClock, Clock3, Copy, History, MapPinned, QrCode, ReceiptText, XCircle } from 'lucide-react';
import { useAuth } from '../../context/auth-context';
import { invoiceService, reservationService, sessionService, waitlistService } from '../../services/api';
import type { ChargingSessionStatus, Invoice, Reservation, WaitlistStatus } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, formatDateTime, parseUtc, shortId } from '../../lib/format';
import { ActiveSessionCard } from '../../components/ActiveSessionCard';
import { StartSessionModal } from '../../components/StartSessionModal';
import { WaitlistStatusCard } from '../../components/WaitlistStatusCard';
import { Badge } from '../../ui/Badge';
import { statusTone } from '../../lib/status';
import { Button } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';
import { Field } from '../../ui/Field';

import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

function arrivalLabel(expiresAt: string) {
  const milliseconds = parseUtc(expiresAt).getTime() - Date.now();
  if (milliseconds <= 0) return 'Expiry is being processed';
  const minutes = Math.max(1, Math.ceil(milliseconds / 60000));
  return `${minutes} minute${minutes === 1 ? '' : 's'} remaining`;
}

export function Sessions() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [waitlistStatus, setWaitlistStatus] = useState<WaitlistStatus | null>(null);
  const [activeSession, setActiveSession] = useState<ChargingSessionStatus | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [cancelling, setCancelling] = useState<Reservation | null>(null);
  const [cancelReason, setCancelReason] = useState('Standard');
  const [isCancelling, setIsCancelling] = useState(false);

  const [isLeavingWaitlist, setIsLeavingWaitlist] = useState(false);
  const [isConfirmingOffer, setIsConfirmingOffer] = useState(false);
  const [startingReservation, setStartingReservation] = useState<Reservation | null>(null);
  const [isStartingSession, setIsStartingSession] = useState(false);
  const [isStoppingSession, setIsStoppingSession] = useState(false);
  const [isPayingInvoices, setIsPayingInvoices] = useState(false);
  const { pushToast } = useToast();
  const { refreshUser } = useAuth();
  const navigate = useNavigate();

  const loadReservations = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const [active, waitlist, session, invoiceList] = await Promise.all([
        reservationService.getActive(),
        waitlistService.getStatus().catch(() => null),
        sessionService.getActive().catch(() => null),
        invoiceService.list().catch(() => []),
      ]);
      setReservations(active);
      setWaitlistStatus(waitlist);
      setActiveSession(session);
      setInvoices(invoiceList);
      // Escrow holds, refunds, and invoice settlements all move the wallet
      // balance; keep the sidebar balance card in sync whenever this reloads.
      void refreshUser();
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Active reservations could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, [refreshUser]);

  useEffect(() => { void loadReservations(); }, [loadReservations]);

  const activeWaitlistId = waitlistStatus?.waitlist_id ?? null;
  useEffect(() => {
    if (!activeWaitlistId) return;
    const interval = setInterval(() => {
      waitlistService.getStatus().then(setWaitlistStatus).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [activeWaitlistId]);

  const activeSessionId = activeSession?.session_id ?? null;
  useEffect(() => {
    if (!activeSessionId) return;
    const interval = setInterval(() => {
      sessionService.getActive().then(setActiveSession).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [activeSessionId]);

  const handleStartSession = async (
    initialPercentage: number,
    targetPercentage: number,
    qrCode: string,
    latitude: number,
    longitude: number,
  ) => {
    if (!startingReservation) return;
    setIsStartingSession(true);
    try {
      const session = await sessionService.start({
        reservation_id: startingReservation.reservation_id,
        initial_battery_percentage: initialPercentage,
        target_battery_percentage: targetPercentage,
        qr_code: qrCode,
        latitude,
        longitude,
      });
      setActiveSession(session);
      setStartingReservation(null);
      await loadReservations();
      pushToast({ title: 'Charging started', message: 'Waiting for charger handshake...', tone: 'success' });
      // FR-15: simulate hardware handshake ack after a 2-second delay
      if (session?.session_id) {
        setTimeout(async () => {
          try {
            await sessionService.hardwareAck(session.session_id);
          } catch {
            /* worker will handle timeout */
          }
        }, 2000);
      }
    } catch (startError) {
      pushToast({ title: 'Couldn\'t start charging', message: getErrorMessage(startError, 'Check your wallet balance and try again.'), tone: 'error' });
    } finally {
      setIsStartingSession(false);
    }
  };

  const handleStopSession = async () => {
    setIsStoppingSession(true);
    try {
      const invoice = await sessionService.stop();
      setActiveSession(null);
      await loadReservations();
      pushToast({
        title: 'Charging stopped',
        message: invoice.is_paid ? `Invoice of ${formatCurrency(invoice.total_amount)} settled from your wallet.` : `Invoice of ${formatCurrency(invoice.total_amount)} exceeds your balance — your account is suspended until it's paid.`,
        tone: invoice.is_paid ? 'success' : 'error',
      });
    } catch (stopError) {
      pushToast({ title: 'Couldn’t stop charging', message: getErrorMessage(stopError, 'Try again.'), tone: 'error' });
    } finally {
      setIsStoppingSession(false);
    }
  };

  const handlePayInvoices = async () => {
    setIsPayingInvoices(true);
    try {
      await invoiceService.payOutstanding();
      await loadReservations();
      pushToast({ title: 'Outstanding invoices settled', tone: 'success' });
    } catch (payError) {
      pushToast({ title: 'Couldn’t settle invoices', message: getErrorMessage(payError, 'Top up your wallet first.'), tone: 'error' });
    } finally {
      setIsPayingInvoices(false);
    }
  };

  const handleLeaveWaitlist = async () => {
    setIsLeavingWaitlist(true);
    try {
      await waitlistService.leave();
      setWaitlistStatus(null);
      pushToast({ title: 'Left the waitlist', tone: 'success' });
    } catch (leaveError) {
      pushToast({ title: 'Couldn’t leave the waitlist', message: getErrorMessage(leaveError, 'Try again.'), tone: 'error' });
    } finally {
      setIsLeavingWaitlist(false);
    }
  };

  const handleConfirmOffer = async () => {
    if (!waitlistStatus) return;
    setIsConfirmingOffer(true);
    try {
      await waitlistService.confirmOffer(waitlistStatus.waitlist_id);
      setWaitlistStatus(null);
      pushToast({ title: 'Reservation confirmed', message: 'Your ₹1,000 escrow is held. Arrive and plug in within 15 minutes.', tone: 'success' });
      await loadReservations();
      navigate('/driver/sessions');
    } catch (confirmError) {
      pushToast({ title: 'Couldn’t confirm the offer', message: getErrorMessage(confirmError, 'The offer may have expired.'), tone: 'error' });
    } finally {
      setIsConfirmingOffer(false);
    }
  };

  const handleCopyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      pushToast({ title: 'Check-in code copied', tone: 'success' });
    } catch {
      pushToast({ title: 'Couldn’t copy the code', message: 'Copy it manually instead.', tone: 'error' });
    }
  };

  const handleCancel = async () => {
    if (!cancelling) return;
    setIsCancelling(true);
    try {
      const reasonToSend = cancelReason === 'Standard' ? undefined : cancelReason;
      const res = await reservationService.cancel(cancelling.reservation_id, reasonToSend);
      setCancelling(null);
      setCancelReason('Standard');
      await loadReservations();
      pushToast({ title: 'Reservation cancelled', message: res?.message || 'Your wallet activity shows whether the escrow was refunded or forfeited.', tone: 'success' });
    } catch (cancelError) {
      pushToast({ title: 'Couldn’t cancel the reservation', message: getErrorMessage(cancelError, 'The reservation state may have changed.'), tone: 'error' });
    } finally {
      setIsCancelling(false);
    }
  };


  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Activity" title="Reservations & charging" description="Time-sensitive reservations appear first, followed by your charging history when available." actions={<Link to="/driver/search"><Button variant="primary" icon={<MapPinned size={18} />}>Find charging</Button></Link>} />

      {waitlistStatus && (
        <WaitlistStatusCard
          status={waitlistStatus}
          onConfirm={() => void handleConfirmOffer()}
          onLeave={() => void handleLeaveWaitlist()}
          isConfirming={isConfirmingOffer}
          isLeaving={isLeavingWaitlist}
        />
      )}

      {activeSession && (
        <ActiveSessionCard status={activeSession} onStop={() => void handleStopSession()} isStopping={isStoppingSession} />
      )}

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
                    {reservation.station_name && <p className="mb-1 text-sm font-bold text-[var(--teal-dark)]">{reservation.station_name}{reservation.connector_type ? ` · ${reservation.connector_type}` : ''}</p>}
                    {reservation.status !== 'Active' && (
                      <>
                        <h3 className="font-display text-xl font-bold">Arrive by {formatDateTime(reservation.expires_at)}</h3>
                        <p className="mt-1 flex items-center gap-1.5 text-sm font-semibold text-[#78560b]"><Clock3 size={16} /> {arrivalLabel(reservation.expires_at)}</p>
                      </>
                    )}
                  </div>
                  {reservation.status === 'Active' ? (
                    <Badge tone="warning">Charging in progress</Badge>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      <Button variant="primary" icon={<BatteryCharging size={17} />} onClick={() => setStartingReservation(reservation)}>Start charging</Button>
                      <Button variant="danger" icon={<XCircle size={17} />} onClick={() => setCancelling(reservation)}>Cancel reservation</Button>
                    </div>
                  )}
                </div>
                <dl className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Charger</dt><dd className="font-data mt-1 truncate font-bold">{reservation.charger_type ?? 'N/A'}{reservation.connector_type ? ` · ${reservation.connector_type}` : ''}</dd></div>
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Station</dt><dd className="font-data mt-1 truncate font-bold">{reservation.station_name ?? 'N/A'}</dd></div>
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Vehicle</dt><dd className="font-data mt-1 truncate font-bold">{reservation.vehicle_name ?? shortId(reservation.vehicle_id, 12)}</dd></div>
                  <div className="surface-muted p-3.5"><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Tariff</dt><dd className="font-data mt-1 font-bold">{formatCurrency(reservation.reserved_tariff)}/kWh</dd></div>
                </dl>
                {reservation.status === 'Confirmed' && reservation.port_qr_code && (
                  <div className="mt-3 flex flex-wrap items-center gap-3 rounded-[var(--radius-md)] border border-dashed border-[var(--teal)]/40 bg-[var(--teal-soft)] p-3.5">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-white text-[var(--teal-dark)]"><QrCode size={22} /></span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Port check-in code</p>
                      <p className="font-data truncate text-sm font-bold text-[var(--ink)]" title={reservation.port_qr_code}>{reservation.port_qr_code}</p>
                      <p className="mt-0.5 text-xs text-[var(--steel)]">This is the QR shown on the physical charger. It’s filled in for you when you start charging.</p>
                    </div>
                    <Button size="sm" variant="secondary" icon={<Copy size={15} />} onClick={() => void handleCopyCode(reservation.port_qr_code as string)}>Copy</Button>
                  </div>
                )}
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="surface overflow-hidden">
        <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Invoices" description="Generated automatically when a charging session ends." /></div>
        {invoices.length === 0 ? (
          <EmptyState title="No invoices yet" description="Start a charging session to generate your first invoice." icon={<History size={23} />} />
        ) : (
          <div className="divide-y divide-[var(--line)]">
            {invoices.some((invoice) => !invoice.is_paid) && (
              <div className="flex flex-wrap items-center justify-between gap-3 bg-[var(--red-soft)] p-4 sm:p-5">
                <p className="text-sm font-bold text-[var(--red-dark)]">One or more invoices are unpaid. Your account is suspended until they're settled.</p>
                <Button variant="danger" onClick={() => void handlePayInvoices()} isLoading={isPayingInvoices}>Settle from wallet</Button>
              </div>
            )}
            {invoices.map((invoice) => (
              <div key={invoice.invoice_id} className="flex items-center gap-4 px-5 py-4 sm:px-6">
                <span className={`flex size-10 shrink-0 items-center justify-center rounded-full ${invoice.is_paid ? 'bg-[var(--teal-soft)] text-[var(--teal-dark)]' : 'bg-[var(--red-soft)] text-[var(--red)]'}`}><ReceiptText size={18} /></span>
                <div className="min-w-0 flex-1"><p className="truncate font-bold">{formatDateTime(invoice.created_at)}</p><p className="font-data text-xs text-[var(--steel)]" title={invoice.invoice_id}>{shortId(invoice.invoice_id, 12)}</p></div>
                <div className="text-right"><p className="font-data font-bold">{formatCurrency(invoice.total_amount)}</p><Badge tone={invoice.is_paid ? 'success' : 'danger'}>{invoice.is_paid ? 'Paid' : 'Unpaid'}</Badge></div>
                <a
                  href={`${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'}/invoices/${invoice.invoice_id}/pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-2 flex items-center gap-1 rounded-md border border-[var(--line)] bg-[var(--paper)] px-2.5 py-1.5 text-xs font-semibold text-[var(--ink)] hover:bg-[var(--surface-muted)] transition-colors"
                  title="Download PDF"
                  onClick={(e) => {
                    const token = localStorage.getItem('token');
                    if (token) {
                      e.preventDefault();
                      const url = `${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'}/invoices/${invoice.invoice_id}/pdf`;
                      fetch(url, { headers: { Authorization: `Bearer ${token}` } })
                        .then(r => {
                          if (!r.ok) throw new Error('Invoice PDF not available');
                          return r.blob();
                        })
                        .then(blob => {
                          const a = document.createElement('a');
                          a.href = URL.createObjectURL(blob);
                          a.download = `electra-invoice-${invoice.invoice_id.slice(0, 8).toUpperCase()}.pdf`;
                          a.click();
                        })
                        .catch((pdfErr) => {
                          pushToast({
                            title: 'Download failed',
                            message: getErrorMessage(pdfErr, 'Could not download invoice PDF.'),
                            tone: 'error',
                          });
                        });
                    }
                  }}

                >
                  ↓ PDF
                </a>
              </div>
            ))}
          </div>
        )}
      </section>

      <Dialog
        open={Boolean(cancelling)}
        onClose={() => setCancelling(null)}
        title="Cancel this reservation?"
        description="The backend decides whether the ₹1,000 escrow is refunded based on how long the port was held and your recent cancellation history. Trusted accounts cancelling for a Faulty Charger or Blocked Bay within 5 minutes receive an automatic cooldown waiver."
        size="sm"
        preventClose={isCancelling}
        footer={
          <>
            <Button onClick={() => setCancelling(null)} disabled={isCancelling}>Keep reservation</Button>
            <Button variant="danger" onClick={() => void handleCancel()} isLoading={isCancelling}>Cancel reservation</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Cancellation Reason" hint="Select a reason for cancelling this reservation.">
            {({ id: inputId, describedBy }) => (
              <select
                id={inputId}
                aria-describedby={describedBy}
                className="field-control"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                disabled={isCancelling}
              >
                <option value="Standard">Standard / Change of plans</option>
                <option value="Faulty Charger">Faulty Charger (Hardware defect / not working)</option>
                <option value="Blocked Bay">Blocked Bay (ICE'd or obstructed)</option>
                <option value="Other">Other reason</option>
              </select>
            )}
          </Field>
          {(cancelReason === 'Faulty Charger' || cancelReason === 'Blocked Bay') && (
            <div className="rounded-lg bg-[var(--amber-soft)] p-3 text-xs font-medium text-[#6f500c]">
              Trusted accounts with cancellations under 5 minutes will receive an immediate escrow refund and a station cooldown waiver (up to 2/day).
            </div>
          )}
        </div>
      </Dialog>


      <StartSessionModal
        open={Boolean(startingReservation)}
        onClose={() => setStartingReservation(null)}
        onConfirm={(initialPercentage, targetPercentage, qrCode, latitude, longitude) => void handleStartSession(initialPercentage, targetPercentage, qrCode, latitude, longitude)}
        portQrCode={startingReservation?.port_qr_code ?? startingReservation?.port_qr_token ?? ''}
        isLoading={isStartingSession}
      />
    </div>
  );
}

export default Sessions;
