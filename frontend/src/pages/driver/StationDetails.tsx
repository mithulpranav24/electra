import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Clock3, Heart, MapPin, PlugZap, ShieldAlert, WalletCards, Zap } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { favoriteService, reservationService, searchService, vehicleService } from '../../services/api';
import type { ChargingPort, Reservation, Station, Vehicle } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, normalizeConnector, vehicleId } from '../../lib/format';
import { ReservationModal } from '../../components/ReservationModal';
import { Alert, EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { Badge, statusTone } from '../../ui/Badge';
import { Button, IconButton } from '../../ui/Button';
import { SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

interface StationPageData {
  station: Station;
  vehicles: Vehicle[];
  activeReservations: Reservation[];
}

export function StationDetails() {
  const { id = '' } = useParams<{ id: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const [data, setData] = useState<StationPageData | null>(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isFavorite, setIsFavorite] = useState(false);
  const [isTogglingFavorite, setIsTogglingFavorite] = useState(false);
  const [selectedPort, setSelectedPort] = useState<ChargingPort | null>(null);
  const [selectedVehicleId, setSelectedVehicleId] = useState('');
  const [isReserving, setIsReserving] = useState(false);

  const loadStation = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const [station, vehicles, activeReservations, favorites] = await Promise.all([
        searchService.getStation(id),
        vehicleService.getVehicles(),
        reservationService.getActive(),
        favoriteService.getFavorites().catch(() => []),
      ]);
      setData({ station, vehicles, activeReservations });
      setIsFavorite(favorites.some((favorite) => favorite.station_id === id));
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Station details could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => { void loadStation(); }, [loadStation]);

  const compatibleVehicles = useMemo(() => {
    if (!selectedPort || !data) return [];
    return data.vehicles.filter((vehicle) => normalizeConnector(vehicle.connector_type) === normalizeConnector(selectedPort.connector_type));
  }, [data, selectedPort]);

  const openReservation = (port: ChargingPort) => {
    setSelectedPort(port);
    const compatible = data?.vehicles.filter((vehicle) => normalizeConnector(vehicle.connector_type) === normalizeConnector(port.connector_type)) ?? [];
    const preferred = compatible.find((vehicle) => vehicle.is_default) ?? compatible[0];
    setSelectedVehicleId(preferred ? vehicleId(preferred) : '');
  };

  const handleFavorite = async () => {
    if (!id) return;
    setIsTogglingFavorite(true);
    try {
      if (isFavorite) await favoriteService.removeFavorite(id);
      else await favoriteService.addFavorite(id);
      setIsFavorite((value) => !value);
      pushToast({ title: isFavorite ? 'Removed from saved stations' : 'Station saved', tone: 'success' });
    } catch (favoriteError) {
      pushToast({ title: 'Couldn’t update saved stations', message: getErrorMessage(favoriteError, 'Try again.'), tone: 'error' });
    } finally {
      setIsTogglingFavorite(false);
    }
  };

  const handleReserve = async () => {
    if (!selectedPort || !selectedVehicleId) return;
    setIsReserving(true);
    try {
      await reservationService.create({ port_id: selectedPort.port_id, vehicle_id: selectedVehicleId });
      setSelectedPort(null);
      pushToast({ title: 'Reservation confirmed', message: 'Your ₹1,000 escrow is held. Arrive and plug in within 15 minutes.', tone: 'success' });
      navigate('/driver/sessions');
    } catch (reserveError) {
      pushToast({ title: 'Couldn’t reserve the port', message: getErrorMessage(reserveError, 'The port may no longer be available.'), tone: 'error' });
    } finally {
      setIsReserving(false);
    }
  };

  if (isLoading) return <div className="surface"><LoadingState label="Loading station" /></div>;
  if (error || !data) return <ErrorState title="Station unavailable" description={error || 'The station was not found.'} onRetry={() => void loadStation()} />;

  const { station, activeReservations } = data;
  const availableCount = station.ports.filter((port) => port.status === 'Available' && port.is_active).length;
  const hours = station.opening_time_local && station.closing_time_local ? `${station.opening_time_local.slice(0, 5)}–${station.closing_time_local.slice(0, 5)}` : 'Open 24 hours';

  return (
    <div className="flex flex-col gap-6 enter-up">
      <Link to="/driver/search" className="inline-flex w-fit items-center gap-1.5 text-sm font-bold text-[var(--teal-dark)] hover:underline"><ArrowLeft size={17} /> Back to station search</Link>

      <section className="overflow-hidden rounded-[var(--radius-lg)] bg-[var(--night)] text-white shadow-[var(--shadow-md)]">
        <div className="flex flex-col gap-5 p-5 sm:p-7 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap gap-2"><Badge tone={availableCount > 0 ? 'success' : 'neutral'}>{availableCount} available</Badge>{station.locked_gate && <Badge tone="warning">Locked gate</Badge>}</div>
            <h1 className="font-display text-3xl font-bold tracking-[-0.035em] sm:text-4xl">{station.name}</h1>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-white/65">
              <span className="font-data flex items-center gap-1.5"><Zap size={16} className="text-[var(--amber)]" /> {formatCurrency(station.price_per_kwh)}/kWh</span>
              <span className="flex items-center gap-1.5"><Clock3 size={16} /> {hours}</span>
              <span className="font-data flex items-center gap-1.5"><MapPin size={16} /> {station.lat.toFixed(4)}, {station.lng.toFixed(4)}</span>
            </div>
          </div>
          <IconButton label={isFavorite ? 'Remove from saved stations' : 'Save station'} onClick={() => void handleFavorite()} disabled={isTogglingFavorite} className={`border-white/15 ${isFavorite ? '!bg-[var(--red-soft)] !text-[var(--red)]' : '!bg-white/10 !text-white hover:!bg-white/20'}`}><Heart size={20} fill={isFavorite ? 'currentColor' : 'none'} /></IconButton>
        </div>
        <dl className="grid border-t border-white/10 sm:grid-cols-3">
          <div className="border-b border-white/10 px-5 py-4 sm:border-b-0 sm:border-r sm:px-7"><dt className="text-xs font-bold uppercase tracking-[0.1em] text-white/45">Ports</dt><dd className="font-data mt-1 text-xl font-bold">{station.ports.length}</dd></div>
          <div className="border-b border-white/10 px-5 py-4 sm:border-b-0 sm:border-r sm:px-7"><dt className="text-xs font-bold uppercase tracking-[0.1em] text-white/45">Minimum session fee</dt><dd className="font-data mt-1 text-xl font-bold">{formatCurrency(station.minimum_session_fee)}</dd></div>
          <div className="px-5 py-4 sm:px-7"><dt className="text-xs font-bold uppercase tracking-[0.1em] text-white/45">Timezone</dt><dd className="font-data mt-1 text-xl font-bold">{station.timezone}</dd></div>
        </dl>
      </section>

      {activeReservations.length > 0 && (
        <Alert tone="warning" title="You already have an active reservation">
          Electra permits one active reservation per driver. <Link to="/driver/sessions" className="font-bold underline">Review your current reservation</Link> before booking another port.
        </Alert>
      )}

      <section className="surface overflow-hidden">
        <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Charging ports" description="Warnings stay visible so you can make an informed manual choice." /></div>
        {station.ports.length === 0 ? (
          <EmptyState title="No ports at this station" description="The operator has not published any active charging ports here." icon={<PlugZap size={22} />} />
        ) : (
          <div className="grid gap-4 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-3">
            {station.ports.map((port) => {
              const isAvailable = port.status === 'Available' && port.is_active && !port.is_pending_maintenance;
              const hasWarning = port.has_health_warning || port.has_blocked_warning;
              return (
                <article key={port.port_id} className={`rounded-[var(--radius-md)] border p-4 ${isAvailable ? 'border-[var(--teal)]/30 bg-[#fbfdfc]' : 'border-[var(--line)] bg-[var(--paper-muted)]'}`}>
                  <div className="flex items-start justify-between gap-3"><div><h3 className="font-display text-lg font-bold">{port.connector_type}</h3><p className="mt-0.5 text-sm text-[var(--steel)]">{port.charger_type}</p></div><Badge tone={statusTone(port.status)}>{port.status}</Badge></div>
                  <p className="font-data mt-4 truncate rounded-md bg-white px-2.5 py-2 text-xs text-[var(--steel-dark)]" title={port.qr_code}>QR {port.qr_code}</p>
                  {hasWarning && <div className="mt-3 flex gap-2 rounded-lg bg-[var(--amber-soft)] p-2.5 text-xs font-semibold text-[#6f500c]"><ShieldAlert size={16} className="shrink-0" /><span>{port.has_health_warning ? 'Health issue reported' : 'Blocked bay reported'}. This port remains a manual option.</span></div>}
                  <Button className="mt-4 w-full" variant={isAvailable ? 'primary' : 'secondary'} disabled={!isAvailable || activeReservations.length > 0} icon={<WalletCards size={16} />} onClick={() => openReservation(port)}>{isAvailable ? 'Reserve port' : 'Unavailable'}</Button>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <ReservationModal
        open={Boolean(selectedPort)}
        onClose={() => setSelectedPort(null)}
        onConfirm={() => void handleReserve()}
        stationName={station.name}
        port={selectedPort}
        pricePerKwh={station.price_per_kwh}
        vehicles={compatibleVehicles}
        selectedVehicleId={selectedVehicleId}
        onVehicleChange={setSelectedVehicleId}
        walletBalance={user?.wallet_balance ?? 0}
        isLoading={isReserving}
      />
    </div>
  );
}
