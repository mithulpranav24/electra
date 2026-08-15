import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BatteryCharging, Car, Clock3, History, MapPinned, ReceiptText, Wallet, Zap } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { authService, reservationService, vehicleService } from '../../services/api';
import type { DriverDashboardData, Reservation, Vehicle } from '../../types';
import { formatCurrency, formatDateTime, shortId } from '../../lib/format';
import { getErrorMessage } from '../../lib/errors';
import { Alert, EmptyState, ErrorState, Skeleton } from '../../ui/Feedback';
import { Badge, statusTone } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { PageHeader, SectionHeader } from '../../ui/Page';

interface DashboardState {
  data: DriverDashboardData;
  reservations: Reservation[];
  vehicles: Vehicle[];
}

function Metric({ label, value, note, icon, tone }: { label: string; value: ReactNode; note: string; icon: ReactNode; tone: 'teal' | 'amber' | 'blue' | 'neutral' }) {
  const styles = {
    teal: 'bg-[var(--teal-soft)] text-[var(--teal-dark)]',
    amber: 'bg-[var(--amber-soft)] text-[#6a4b08]',
    blue: 'bg-[var(--blue-soft)] text-[#285270]',
    neutral: 'bg-[var(--paper-muted)] text-[var(--steel-dark)]',
  };
  return (
    <div className="surface p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-extrabold uppercase tracking-[0.11em] text-[var(--steel)]">{label}</p>
        <span className={`flex size-9 items-center justify-center rounded-full ${styles[tone]}`}>{icon}</span>
      </div>
      <div className="font-data mt-4 text-2xl font-bold tracking-tight">{value}</div>
      <p className="mt-1 text-xs text-[var(--steel)]">{note}</p>
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [state, setState] = useState<DashboardState | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const [data, reservations, vehicles] = await Promise.all([
        authService.getDashboardData(),
        reservationService.getActive(),
        vehicleService.getVehicles(),
      ]);
      setState({ data, reservations, vehicles });
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Your charging overview could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void loadDashboard(); }, [loadDashboard]);

  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'driver';
  const defaultVehicle = state?.vehicles.find((vehicle) => vehicle.is_default) ?? state?.vehicles[0];
  const activeReservation = state?.reservations[0];

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Driver home" title={`Ready when you are, ${firstName}.`} description="Check your charging readiness, then take the next step." actions={<Link to="/driver/search"><Button variant="primary" size="lg" icon={<MapPinned size={19} />}>Find charging</Button></Link>} />

      {error && !state && <ErrorState description={error} onRetry={() => void loadDashboard()} />}

      {isLoading && !state ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Loading dashboard">
          {Array.from({ length: 4 }).map((_, index) => <div key={index} className="surface p-5"><Skeleton className="h-3 w-28" /><Skeleton className="mt-5 h-8 w-20" /><Skeleton className="mt-2 h-3 w-36" /></div>)}
        </div>
      ) : state && (
        <>
          {(user?.wallet_balance ?? 0) < 1000 && (
            <Alert tone="warning" title="Top up before reserving">
              Your wallet needs at least ₹1,000 for the reservation escrow. <Link to="/driver/wallet" className="font-bold underline">Add funds</Link>
            </Alert>
          )}
          {state.vehicles.length === 0 && (
            <Alert tone="info" title="Add a vehicle to see compatible ports">
              Charging searches work best when Electra knows your connector. <Link to="/driver/vehicles" className="font-bold underline">Add your first vehicle</Link>
            </Alert>
          )}

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Charging overview">
            <Metric label="Wallet ready" value={formatCurrency(user?.wallet_balance ?? 0, 0)} note={(user?.wallet_balance ?? 0) >= 1000 ? 'Ready for reservation escrow' : '₹1,000 minimum to reserve'} icon={<Wallet size={18} />} tone={(user?.wallet_balance ?? 0) >= 1000 ? 'teal' : 'amber'} />
            <Metric label="Active session" value={state.data.active_sessions || 'None'} note="Current charging activity" icon={<BatteryCharging size={18} />} tone={state.data.active_sessions ? 'teal' : 'neutral'} />
            <Metric label="Upcoming" value={state.reservations.length || state.data.upcoming_bookings || 'None'} note="Confirmed reservations" icon={<Clock3 size={18} />} tone={state.reservations.length ? 'amber' : 'neutral'} />
            <Metric label="Energy this month" value={<>{Number(state.data.energy_charged_kwh ?? 0).toLocaleString('en-IN')} <span className="text-base">kWh</span></>} note={`${state.data.unpaid_invoices ?? 0} unpaid invoice${Number(state.data.unpaid_invoices ?? 0) === 1 ? '' : 's'}`} icon={<Zap size={18} />} tone="blue" />
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(19rem,0.65fr)]">
            <div className="surface overflow-hidden">
              <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Next charging step" description="Electra puts the time-sensitive item first." /></div>
              {activeReservation ? (
                <div className="p-5 sm:p-6">
                  <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="mb-3 flex items-center gap-2"><Badge tone={statusTone(activeReservation.status)}>{activeReservation.status}</Badge><span className="font-data text-xs text-[var(--steel)]">Port {shortId(activeReservation.port_id)}</span></div>
                      <h3 className="font-display text-2xl font-bold">Arrive before {new Date(activeReservation.expires_at).toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit' })}</h3>
                      <p className="mt-1 text-sm text-[var(--steel)]">Reserved {formatDateTime(activeReservation.created_at)}. Open activity to review cancellation details.</p>
                    </div>
                    <Link to="/driver/sessions"><Button variant="primary" icon={<ArrowRight size={17} />}>View reservation</Button></Link>
                  </div>
                </div>
              ) : (
                <div className="p-5 sm:p-6">
                  <div className="rounded-[var(--radius-md)] bg-[var(--night)] p-5 text-white sm:p-6">
                    <p className="text-xs font-extrabold uppercase tracking-[0.14em] text-[var(--amber)]">No active booking</p>
                    <h3 className="font-display mt-2 text-2xl font-bold">Find a port that fits your route.</h3>
                    <p className="mt-2 max-w-xl text-sm text-white/65">Compare availability, connector type, charging speed, and tariff before you commit.</p>
                    <Link to="/driver/search" className="mt-5 inline-block"><Button variant="primary" className="!border-[var(--amber)] !bg-[var(--amber)] !text-[var(--night)] hover:!bg-[#dca21d]" icon={<MapPinned size={17} />}>Explore stations</Button></Link>
                  </div>
                </div>
              )}
            </div>

            <div className="surface p-5 sm:p-6">
              <SectionHeader title="Charging readiness" description="The essentials used during reservation." />
              <div className="mt-5 flex flex-col gap-3">
                <Link to="/driver/vehicles" className="interactive-row flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--line)] p-3.5">
                  <span className="flex size-10 items-center justify-center rounded-full bg-[var(--paper-muted)] text-[var(--teal)]"><Car size={19} /></span>
                  <span className="min-w-0 flex-1"><span className="block text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Vehicle</span><span className="block truncate font-bold">{defaultVehicle ? [defaultVehicle.make, defaultVehicle.model].filter(Boolean).join(' ') || defaultVehicle.license_plate : 'Not set up'}</span></span>
                  <ArrowRight size={17} className="text-[var(--steel)]" />
                </Link>
                <Link to="/driver/wallet" className="interactive-row flex items-center gap-3 rounded-[var(--radius-md)] border border-[var(--line)] p-3.5">
                  <span className="flex size-10 items-center justify-center rounded-full bg-[var(--paper-muted)] text-[var(--teal)]"><Wallet size={19} /></span>
                  <span className="min-w-0 flex-1"><span className="block text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Wallet</span><span className="font-data block truncate font-bold">{formatCurrency(user?.wallet_balance ?? 0)}</span></span>
                  <ArrowRight size={17} className="text-[var(--steel)]" />
                </Link>
              </div>
            </div>
          </section>

          <section className="surface overflow-hidden">
            <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Recent activity" description="Charging and billing updates from your account." action={<Link to="/driver/sessions" className="inline-flex items-center gap-1 text-sm font-bold text-[var(--teal-dark)] hover:underline">View all <ArrowRight size={15} /></Link>} /></div>
            {state.data.recent_activity?.length ? (
              <div className="divide-y divide-[var(--line)]">
                {state.data.recent_activity.map((activity) => (
                  <div key={activity.id} className="flex items-center gap-4 px-5 py-4 sm:px-6">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[var(--teal-soft)] text-[var(--teal-dark)]"><History size={18} /></span>
                    <div className="min-w-0 flex-1"><p className="truncate font-bold">{activity.location}</p><p className="text-xs text-[var(--steel)]">{activity.date}</p></div>
                    <div className="text-right"><p className="font-data font-bold">{activity.amount}</p><Badge tone={statusTone(activity.status)}>{activity.status}</Badge></div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState compact title="No charging activity yet" description="Completed charges, billing events, and account updates will appear here." icon={<ReceiptText size={22} />} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
