import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircleMarker, MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';
import { ArrowRight, Clock3, Filter, Heart, List, LocateFixed, Map, MapPin, PlugZap, Search, Zap } from 'lucide-react';
import { favoriteService, searchService } from '../../services/api';
import type { Favorite, Station } from '../../types';
import { getErrorMessage } from '../../lib/errors';
import { formatCurrency } from '../../lib/format';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { EmptyState, ErrorState, LoadingState } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { PageHeader, SectionHeader } from '../../ui/Page';

const stationIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -35] });
const userLat = 12.9716;
const userLng = 77.5946;

function availablePorts(station: Station) {
  return station.ports.filter((port) => port.is_active && port.status === 'Available').length;
}

function StationResult({ station, active, onOpen, onSelect }: { station: Station; active: boolean; onOpen: () => void; onSelect: () => void }) {
  const available = availablePorts(station);
  const hasWarnings = station.ports.some((port) => port.has_health_warning || port.has_blocked_warning);
  return (
    <article className={`interactive-row rounded-[var(--radius-md)] border bg-white p-4 ${active ? 'border-[var(--teal)] shadow-sm' : 'border-[var(--line)]'}`}>
      <button type="button" className="w-full text-left" onClick={onSelect} aria-pressed={active}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0"><h3 className="font-display truncate text-lg font-bold">{station.name}</h3><p className="mt-1 flex items-center gap-1 text-xs text-[var(--steel)]"><MapPin size={13} /> {station.lat.toFixed(4)}, {station.lng.toFixed(4)}</p></div>
          <Badge tone={available > 0 ? 'success' : 'neutral'}>{available} available</Badge>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-sm text-[var(--steel-dark)]">
          <span className="font-data flex items-center gap-1.5 font-bold"><Zap size={15} className="text-[var(--teal)]" /> {formatCurrency(station.price_per_kwh)}/kWh</span>
          <span className="flex items-center gap-1.5"><PlugZap size={15} /> {station.ports.length} total ports</span>
          <span className="flex items-center gap-1.5"><Clock3 size={15} /> {station.opening_time_local && station.closing_time_local ? `${station.opening_time_local.slice(0, 5)}–${station.closing_time_local.slice(0, 5)}` : 'Open 24 hours'}</span>
        </div>
        {hasWarnings && <p className="mt-3 text-xs font-semibold text-[#7a580c]">Some ports have a reported issue; review port details before reserving.</p>}
      </button>
      <Button variant="ghost" size="sm" className="mt-3 w-full" icon={<ArrowRight size={15} />} onClick={onOpen}>View station</Button>
    </article>
  );
}

export function SearchStations() {
  const [stations, setStations] = useState<Station[]>([]);
  const [recentStations, setRecentStations] = useState<Station[]>([]);
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [fastOnly, setFastOnly] = useState(false);
  const [connectorType, setConnectorType] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedStationId, setSelectedStationId] = useState('');
  const [mobileView, setMobileView] = useState<'list' | 'map'>('list');
  const navigate = useNavigate();

  const runSearch = useCallback(async (connector: string, fast: boolean) => {
    setError('');
    setIsLoading(true);
    try {
      const results = await searchService.searchStations({ lat: userLat, lng: userLng, radius_km: 500, connector_type: connector || null, min_power_kw: fast ? 50 : null });
      setStations(results);
      setSelectedStationId((current) => results.some((station) => station.station_id === current) ? current : results[0]?.station_id ?? '');
    } catch (searchError) {
      setError(getErrorMessage(searchError, 'Stations could not be searched.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadInitial = useCallback(async () => {
    void runSearch('', false);
    const [recentResult, favoriteResult] = await Promise.allSettled([searchService.getRecentStations(), favoriteService.getFavorites()]);
    if (recentResult.status === 'fulfilled') setRecentStations(recentResult.value);
    if (favoriteResult.status === 'fulfilled') setFavorites(favoriteResult.value);
  }, [runSearch]);

  useEffect(() => { void loadInitial(); }, [loadInitial]);

  const selectedStation = useMemo(() => stations.find((station) => station.station_id === selectedStationId), [selectedStationId, stations]);

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Find charging" title="Choose the right stop" description="Compare compatible stations around Bengaluru before opening the map or committing to a port." />

      <form className="surface grid gap-4 p-4 sm:p-5 lg:grid-cols-[minmax(12rem,1fr)_minmax(12rem,1fr)_auto] lg:items-end" onSubmit={(event) => { event.preventDefault(); void runSearch(connectorType, fastOnly); }}>
        <Field label="Connector type">
          {({ id, describedBy }) => (
            <div className="relative"><Filter size={17} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" /><select id={id} aria-describedby={describedBy} className="field-control pl-10" value={connectorType} onChange={(event) => setConnectorType(event.target.value)}><option value="">Any connector</option><option value="CCS2">CCS 2</option><option value="CHAdeMO">CHAdeMO</option><option value="Type 2">Type 2</option></select></div>
          )}
        </Field>
        <div>
          <span className="field-label mb-1.5">Charging speed</span>
          <label className="flex min-h-[2.875rem] cursor-pointer items-center gap-3 rounded-[var(--radius-sm)] border border-[var(--line-strong)] bg-white px-3.5">
            <input type="checkbox" checked={fastOnly} onChange={(event) => setFastOnly(event.target.checked)} className="size-4 accent-[var(--teal)]" />
            <span className="flex items-center gap-2 text-sm font-bold"><Zap size={17} className="text-[var(--teal)]" /> Fast charging (50 kW+)</span>
          </label>
        </div>
        <Button type="submit" variant="primary" size="lg" icon={<Search size={18} />} isLoading={isLoading}>Search stations</Button>
      </form>

      <div className="flex rounded-xl border border-[var(--line)] bg-white p-1 lg:hidden" aria-label="Search result view">
        <button type="button" className={`flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg text-sm font-bold ${mobileView === 'list' ? 'bg-[var(--night)] text-white' : 'text-[var(--steel)]'}`} onClick={() => setMobileView('list')}><List size={17} /> List</button>
        <button type="button" className={`flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg text-sm font-bold ${mobileView === 'map' ? 'bg-[var(--night)] text-white' : 'text-[var(--steel)]'}`} onClick={() => setMobileView('map')}><Map size={17} /> Map</button>
      </div>

      {error && stations.length === 0 ? <ErrorState title="Search unavailable" description={error} onRetry={() => void runSearch(connectorType, fastOnly)} /> : (
        <section className="grid min-w-0 gap-5 lg:grid-cols-[minmax(20rem,0.8fr)_minmax(0,1.2fr)]">
          <div className={`surface min-w-0 overflow-hidden ${mobileView === 'map' ? 'hidden lg:block' : ''}`}>
            <div className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3.5"><div><h2 className="font-display font-bold">Stations</h2><p className="text-xs text-[var(--steel)]">{isLoading ? 'Updating results…' : `${stations.length} match${stations.length === 1 ? '' : 'es'}`}</p></div>{selectedStation && <Badge tone="info">Selected</Badge>}</div>
            <div className="app-scrollbar flex max-h-[680px] flex-col gap-3 overflow-y-auto p-3">
              {isLoading && stations.length === 0 ? <LoadingState label="Searching stations" /> : stations.length === 0 ? <EmptyState title="No matching stations" description="Try another connector type or include standard-speed chargers." icon={<MapPin size={22} />} /> : stations.map((station) => <StationResult key={station.station_id} station={station} active={station.station_id === selectedStationId} onSelect={() => setSelectedStationId(station.station_id)} onOpen={() => navigate(`/driver/station/${station.station_id}`)} />)}
            </div>
          </div>

          <div className={`surface relative min-w-0 overflow-hidden ${mobileView === 'list' ? 'hidden lg:block' : ''}`} aria-label="Station map">
            <div className="absolute left-3 top-3 z-[500] rounded-full border border-[var(--line)] bg-white/95 px-3 py-2 text-xs font-bold shadow-sm"><LocateFixed size={14} className="mr-1 inline text-[var(--teal)]" /> Bengaluru search center</div>
            <MapContainer center={selectedStation ? [selectedStation.lat, selectedStation.lng] : [userLat, userLng]} zoom={12} className="h-[560px] w-full lg:h-[725px]" scrollWheelZoom>
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <CircleMarker center={[userLat, userLng]} radius={8} pathOptions={{ color: '#ffffff', fillColor: '#087f6d', fillOpacity: 1, weight: 3 }}><Popup><strong>Search center</strong><br />Bengaluru</Popup></CircleMarker>
              {stations.map((station) => (
                <Marker key={station.station_id} position={[station.lat, station.lng]} icon={stationIcon} eventHandlers={{ click: () => setSelectedStationId(station.station_id) }}>
                  <Popup><div className="min-w-44"><strong>{station.name}</strong><p className="my-1">{availablePorts(station)} ports available</p><p className="my-1">{formatCurrency(station.price_per_kwh)}/kWh</p><button type="button" className="mt-2 w-full rounded-md bg-[#087f6d] px-3 py-2 font-bold text-white" onClick={() => navigate(`/driver/station/${station.station_id}`)}>View station</button></div></Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>
        </section>
      )}

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Recently viewed" description="Your five most recent station detail pages." />
          {recentStations.length === 0 ? <EmptyState compact title="No recent stations" description="Stations you inspect will stay here for quick return." icon={<Clock3 size={21} />} /> : <div className="mt-4 flex flex-col gap-2">{recentStations.map((station) => <button key={station.station_id} type="button" className="interactive-row flex min-h-14 items-center gap-3 rounded-lg border border-[var(--line)] p-3 text-left" onClick={() => navigate(`/driver/station/${station.station_id}`)}><span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[var(--paper-muted)] text-[var(--teal)]"><MapPin size={17} /></span><span className="min-w-0 flex-1"><span className="block truncate font-bold">{station.name}</span><span className="font-data block text-xs text-[var(--steel)]">{formatCurrency(station.price_per_kwh)}/kWh</span></span><ArrowRight size={16} className="text-[var(--steel)]" /></button>)}</div>}
        </div>
        <div className="surface p-5 sm:p-6">
          <SectionHeader title="Saved stations" description="Favorites you marked for quick access." />
          {favorites.length === 0 ? <EmptyState compact title="No saved stations" description="Use the heart on a station page to keep it here." icon={<Heart size={21} />} /> : <div className="mt-4 flex flex-col gap-2">{favorites.map((favorite) => <button key={favorite.favorite_id} type="button" className="interactive-row flex min-h-14 items-center gap-3 rounded-lg border border-[var(--line)] p-3 text-left" onClick={() => navigate(`/driver/station/${favorite.station_id}`)}><span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[var(--red-soft)] text-[var(--red)]"><Heart size={17} fill="currentColor" /></span><span className="min-w-0 flex-1"><span className="block truncate font-bold">{favorite.station.name}</span><span className="font-data block text-xs text-[var(--steel)]">{formatCurrency(favorite.station.price_per_kwh)}/kWh</span></span><ArrowRight size={16} className="text-[var(--steel)]" /></button>)}</div>}
        </div>
      </section>
    </div>
  );
}
