import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Clock3, Heart, ListPlus, MapPin, MessageSquare, PlugZap, QrCode, ShieldAlert, Star, WalletCards, Zap } from 'lucide-react';
import { useAuth } from '../../context/auth-context';
import { favoriteService, ratingService, reservationService, searchService, sessionService, vehicleService, waitlistService } from '../../services/api';
import type { ChargingPort, Reservation, Station, StationRatingsResponse, Vehicle, WaitlistStatus } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency, formatDate, normalizeConnector, vehicleId } from '../../lib/format';
import { MOCK_USER_LAT, MOCK_USER_LNG } from '../../lib/geo';
import { ReservationModal } from '../../components/ReservationModal';
import { WaitlistJoinModal } from '../../components/WaitlistJoinModal';
import { WaitlistStatusCard } from '../../components/WaitlistStatusCard';
import { Alert, EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { Badge } from '../../ui/Badge';
import { statusTone } from '../../lib/status';
import { Button, IconButton } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';
import { Field } from '../../ui/Field';
import { SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

interface StationPageData {
  station: Station;
  vehicles: Vehicle[];
  activeReservations: Reservation[];
  waitlistStatus: WaitlistStatus | null;
  ratings: StationRatingsResponse | null;
}

function StarPicker({ label, value, onChange }: { label: string; value: number; onChange: (score: number) => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm font-semibold text-[var(--ink)]">{label}</span>
      <div className="flex gap-1" role="radiogroup" aria-label={label}>
        {[1, 2, 3, 4, 5].map((score) => (
          <button
            key={score}
            type="button"
            role="radio"
            aria-checked={value === score}
            aria-label={`${score} star${score === 1 ? '' : 's'}`}
            onClick={() => onChange(score)}
            className="p-0.5"
          >
            <Star size={22} className={score <= value ? 'fill-[var(--amber)] text-[var(--amber)]' : 'text-[var(--line)]'} />
          </button>
        ))}
      </div>
    </div>
  );
}

function StarRow({ value }: { value: number | null }) {
  if (value === null) return <span className="text-xs text-[var(--steel)]">No ratings yet</span>;
  return (
    <span className="inline-flex items-center gap-1">
      <Star size={16} className="fill-[var(--amber)] text-[var(--amber)]" />
      <span className="font-data text-sm font-bold">{value.toFixed(1)}</span>
    </span>
  );
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
  const [showWaitlistModal, setShowWaitlistModal] = useState(false);
  const [waitlistVehicleId, setWaitlistVehicleId] = useState('');
  const [isJoiningWaitlist, setIsJoiningWaitlist] = useState(false);
  const [isLeavingWaitlist, setIsLeavingWaitlist] = useState(false);
  const [isConfirmingOffer, setIsConfirmingOffer] = useState(false);
  const [ratingForm, setRatingForm] = useState({ overall_score: 0, cleanliness_score: 0, access_score: 0, experience_score: 0, comment: '' });
  const [isSubmittingRating, setIsSubmittingRating] = useState(false);
  const [challengingPort, setChallengingPort] = useState<ChargingPort | null>(null);
  const [challengeQr, setChallengeQr] = useState('');
  const [isChallenging, setIsChallenging] = useState(false);

  const loadStation = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      const [station, vehicles, activeReservations, favorites, waitlistStatus, ratings] = await Promise.all([
        searchService.getStation(id),
        vehicleService.getVehicles(),
        reservationService.getActive(),
        favoriteService.getFavorites().catch(() => []),
        waitlistService.getStatus().catch(() => null),
        ratingService.getStationRatings(id).catch(() => null),
      ]);
      setData({ station, vehicles, activeReservations, waitlistStatus, ratings });
      setIsFavorite(favorites.some((favorite) => favorite.station_id === id));
      if (ratings?.my_rating) {
        setRatingForm({
          overall_score: ratings.my_rating.overall_score,
          cleanliness_score: ratings.my_rating.cleanliness_score,
          access_score: ratings.my_rating.access_score,
          experience_score: ratings.my_rating.experience_score,
          comment: ratings.my_rating.comment ?? '',
        });
      }
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

  const vehiclesNeedingWaitlist = useMemo(() => {
    if (!data) return [];
    return data.vehicles.filter((vehicle) => {
      const matchingPorts = data.station.ports.filter((port) => normalizeConnector(port.connector_type) === normalizeConnector(vehicle.connector_type));
      if (matchingPorts.length === 0) return false;
      const hasUnwarnedAvailable = matchingPorts.some((port) => port.status === 'Available' && port.is_active && !port.has_health_warning && !port.has_blocked_warning);
      return !hasUnwarnedAvailable;
    });
  }, [data]);

  const openWaitlistModal = () => {
    const preferred = vehiclesNeedingWaitlist.find((vehicle) => vehicle.is_default) ?? vehiclesNeedingWaitlist[0];
    setWaitlistVehicleId(preferred ? vehicleId(preferred) : '');
    setShowWaitlistModal(true);
  };

  const handleJoinWaitlist = async () => {
    if (!waitlistVehicleId || !id) return;
    setIsJoiningWaitlist(true);
    try {
      const status = await waitlistService.join({ station_id: id, vehicle_id: waitlistVehicleId, lat: MOCK_USER_LAT, lng: MOCK_USER_LNG });
      setData((current) => current ? { ...current, waitlistStatus: status } : current);
      setShowWaitlistModal(false);
      pushToast({ title: 'Joined the waitlist', message: `You're position ${status.position} in line.`, tone: 'success' });
    } catch (joinError) {
      pushToast({ title: 'Couldn’t join the waitlist', message: getErrorMessage(joinError, 'Try again.'), tone: 'error' });
    } finally {
      setIsJoiningWaitlist(false);
    }
  };

  const handleLeaveWaitlist = async () => {
    setIsLeavingWaitlist(true);
    try {
      await waitlistService.leave();
      setData((current) => current ? { ...current, waitlistStatus: null } : current);
      pushToast({ title: 'Left the waitlist', tone: 'success' });
    } catch (leaveError) {
      pushToast({ title: 'Couldn’t leave the waitlist', message: getErrorMessage(leaveError, 'Try again.'), tone: 'error' });
    } finally {
      setIsLeavingWaitlist(false);
    }
  };

  const handleConfirmOffer = async () => {
    if (!data?.waitlistStatus) return;
    setIsConfirmingOffer(true);
    try {
      await waitlistService.confirmOffer(data.waitlistStatus.waitlist_id);
      pushToast({ title: 'Reservation confirmed', message: 'Your ₹1,000 escrow is held. Arrive and plug in within 15 minutes.', tone: 'success' });
      navigate('/driver/sessions');
    } catch (confirmError) {
      pushToast({ title: 'Couldn’t confirm the offer', message: getErrorMessage(confirmError, 'The offer may have expired.'), tone: 'error' });
    } finally {
      setIsConfirmingOffer(false);
    }
  };

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

  const handleSubmitRating = async () => {
    if (!id || !ratingForm.overall_score || !ratingForm.cleanliness_score || !ratingForm.access_score || !ratingForm.experience_score) {
      pushToast({ title: 'Rate every category', message: 'Overall, cleanliness, access, and experience all need a score.', tone: 'error' });
      return;
    }
    setIsSubmittingRating(true);
    try {
      await ratingService.submitRating(id, { ...ratingForm, comment: ratingForm.comment || null });
      const ratings = await ratingService.getStationRatings(id);
      setData((current) => current ? { ...current, ratings } : current);
      pushToast({ title: 'Thanks for the review', tone: 'success' });
    } catch (ratingError) {
      pushToast({ title: 'Couldn’t submit your rating', message: getErrorMessage(ratingError, 'You may need a completed session here first.'), tone: 'error' });
    } finally {
      setIsSubmittingRating(false);
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

  const handleChallengePort = async () => {
    if (!challengingPort || !challengeQr.trim()) return;
    setIsChallenging(true);
    try {
      const res = await sessionService.challengePort(challengingPort.port_id, {
        qr_code: challengeQr.trim(),
        latitude: MOCK_USER_LAT,
        longitude: MOCK_USER_LNG,
      });
      setChallengingPort(null);
      pushToast({
        title: 'Port Challenge',
        message: res.message || 'Port challenge processed successfully.',
        tone: 'success',
      });
      await loadStation();
      navigate('/driver/sessions');
    } catch (challengeErr) {
      pushToast({
        title: 'Challenge rejected',
        message: getErrorMessage(challengeErr, 'Could not challenge port.'),
        tone: 'error',
      });
    } finally {
      setIsChallenging(false);
    }
  };

  if (isLoading) return <div className="surface"><LoadingState label="Loading station" /></div>;
  if (error || !data) return <ErrorState title="Station unavailable" description={error || 'The station was not found.'} onRetry={() => void loadStation()} />;

  const { station, activeReservations, waitlistStatus } = data;
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
              {data.ratings && data.ratings.summary.rating_count > 0 && (
                <span className="flex items-center gap-1.5"><Star size={16} className="fill-[var(--amber)] text-[var(--amber)]" /> {data.ratings.summary.average_overall?.toFixed(1)} ({data.ratings.summary.rating_count})</span>
              )}
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

      {waitlistStatus && waitlistStatus.station_id === id ? (
        <WaitlistStatusCard
          status={waitlistStatus}
          stationName={station.name}
          onConfirm={() => void handleConfirmOffer()}
          onLeave={() => void handleLeaveWaitlist()}
          isConfirming={isConfirmingOffer}
          isLeaving={isLeavingWaitlist}
        />
      ) : waitlistStatus ? (
        <Alert tone="info" title="You already have an active waitlist entry">
          Electra permits one active waitlist entry per driver. <Link to="/driver/sessions" className="font-bold underline">Review your current waitlist status</Link> before joining another queue.
        </Alert>
      ) : activeReservations.length === 0 && vehiclesNeedingWaitlist.length > 0 && (
        <Alert tone="info" title="This station is fully booked for your vehicle">
          Join the waitlist and Electra will hold a port for you the moment one frees up.
          <div className="mt-3"><Button variant="primary" size="sm" icon={<ListPlus size={16} />} onClick={openWaitlistModal}>Join waitlist</Button></div>
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
                  {port.status === 'Charging' && activeReservations.length === 0 ? (
                    <Button
                      className="mt-4 w-full"
                      variant="secondary"
                      icon={<ShieldAlert size={16} />}
                      onClick={() => {
                        setChallengingPort(port);
                        setChallengeQr(port.qr_token || port.qr_code || '');
                      }}
                    >
                      Challenge Port
                    </Button>
                  ) : (
                    <Button className="mt-4 w-full" variant={isAvailable ? 'primary' : 'secondary'} disabled={!isAvailable || activeReservations.length > 0} icon={<WalletCards size={16} />} onClick={() => openReservation(port)}>{isAvailable ? 'Reserve port' : 'Unavailable'}</Button>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="surface overflow-hidden">
        <div className="border-b border-[var(--line)] p-5 sm:p-6"><SectionHeader title="Ratings & reviews" description="Overall, cleanliness, ease of access, and charging experience, 1–5." /></div>
        <div className="grid gap-6 p-5 sm:p-6 lg:grid-cols-2">
          <div>
            {data.ratings && data.ratings.summary.rating_count > 0 ? (
              <>
                <div className="mb-4 flex items-baseline gap-2">
                  <span className="font-data text-3xl font-bold">{data.ratings.summary.average_overall?.toFixed(1)}</span>
                  <StarRow value={data.ratings.summary.average_overall} />
                  <span className="text-sm text-[var(--steel)]">· {data.ratings.summary.rating_count} review{data.ratings.summary.rating_count === 1 ? '' : 's'}</span>
                </div>
                <dl className="mb-5 grid grid-cols-3 gap-3 text-sm">
                  <div><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Cleanliness</dt><dd className="mt-0.5"><StarRow value={data.ratings.summary.average_cleanliness} /></dd></div>
                  <div><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Access</dt><dd className="mt-0.5"><StarRow value={data.ratings.summary.average_access} /></dd></div>
                  <div><dt className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]">Experience</dt><dd className="mt-0.5"><StarRow value={data.ratings.summary.average_experience} /></dd></div>
                </dl>
                {data.ratings.ratings.length === 0 ? (
                  <p className="text-sm text-[var(--steel)]">No written reviews yet.</p>
                ) : (
                  <ul className="flex flex-col gap-4">
                    {data.ratings.ratings.map((review) => (
                      <li key={review.rating_id} className="rounded-[var(--radius-md)] border border-[var(--line)] p-3.5">
                        <div className="flex items-center justify-between gap-3"><StarRow value={review.overall_score} /><span className="text-xs text-[var(--steel)]">{formatDate(review.created_at)}</span></div>
                        {review.comment && <p className="mt-1.5 text-sm text-[var(--steel-dark)]">{review.comment}</p>}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            ) : (
              <EmptyState compact title="No reviews yet" description="Be the first driver to rate this station." icon={<MessageSquare size={20} />} />
            )}
          </div>

          {user?.role === 'Driver' && (
            <div className="rounded-[var(--radius-md)] border border-[var(--line)] bg-[var(--paper-muted)] p-4 sm:p-5">
              <p className="mb-4 text-sm font-bold">{data.ratings?.my_rating ? 'Update your rating' : 'Rate this station'}</p>
              <div className="flex flex-col gap-3">
                <StarPicker label="Overall" value={ratingForm.overall_score} onChange={(score) => setRatingForm((current) => ({ ...current, overall_score: score }))} />
                <StarPicker label="Cleanliness" value={ratingForm.cleanliness_score} onChange={(score) => setRatingForm((current) => ({ ...current, cleanliness_score: score }))} />
                <StarPicker label="Ease of access" value={ratingForm.access_score} onChange={(score) => setRatingForm((current) => ({ ...current, access_score: score }))} />
                <StarPicker label="Charging experience" value={ratingForm.experience_score} onChange={(score) => setRatingForm((current) => ({ ...current, experience_score: score }))} />
                <textarea
                  className="field-control mt-1 min-h-20 resize-none"
                  placeholder="Share details of your experience (optional)"
                  value={ratingForm.comment}
                  onChange={(event) => setRatingForm((current) => ({ ...current, comment: event.target.value }))}
                />
                <Button variant="primary" onClick={() => void handleSubmitRating()} isLoading={isSubmittingRating}>{data.ratings?.my_rating ? 'Update rating' : 'Submit rating'}</Button>
                <p className="text-xs text-[var(--steel)]">You can only rate stations where you’ve completed a charging session.</p>
              </div>
            </div>
          )}
        </div>
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

      <WaitlistJoinModal
        open={showWaitlistModal}
        onClose={() => setShowWaitlistModal(false)}
        onConfirm={() => void handleJoinWaitlist()}
        stationName={station.name}
        minimumSessionFee={station.minimum_session_fee}
        vehicles={vehiclesNeedingWaitlist}
        selectedVehicleId={waitlistVehicleId}
        onVehicleChange={setWaitlistVehicleId}
        walletBalance={user?.wallet_balance ?? 0}
        isLoading={isJoiningWaitlist}
      />

      <Dialog
        open={Boolean(challengingPort)}
        onClose={() => setChallengingPort(null)}
        title="Challenge Port (Ghost Session)"
        description="If this bay shows 'Charging' in the app but no vehicle is plugged in, scan or enter the port's QR code to verify hardware state. If disconnected, the ghost session will be terminated."
        size="sm"
        preventClose={isChallenging}
        footer={
          <>
            <Button onClick={() => setChallengingPort(null)} disabled={isChallenging}>Cancel</Button>
            <Button variant="primary" onClick={() => void handleChallengePort()} isLoading={isChallenging} disabled={!challengeQr.trim()}>Submit Challenge</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Port QR Token" hint="The unique QR code/token on the physical charger.">
            {({ id: inputId, describedBy }) => (
              <div className="relative">
                <QrCode size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--steel)]" />
                <input
                  id={inputId}
                  aria-describedby={describedBy}
                  type="text"
                  className="field-control pl-10"
                  placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000"
                  value={challengeQr}
                  onChange={(e) => setChallengeQr(e.target.value)}
                  disabled={isChallenging}
                />
              </div>
            )}
          </Field>
          <div className="rounded-lg bg-[var(--paper-muted)] p-3 text-xs text-[var(--steel)]">
            <span className="font-semibold text-[var(--ink)]">Geofence Check:</span> Your GPS location will be verified against the station radius (200m).
          </div>
        </div>
      </Dialog>
    </div>
  );
}

