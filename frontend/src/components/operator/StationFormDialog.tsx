import { useEffect, useState } from 'react';
import { MapContainer, Marker, TileLayer, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import 'leaflet/dist/leaflet.css';
import type { Station } from '../../types';
import { operatorService, type StationPayload } from '../../services/api';
import { getErrorMessage } from '../../lib/errors';
import { Alert } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { Button } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';

const markerIcon = L.icon({ iconUrl: icon, shadowUrl: iconShadow, iconSize: [25, 41], iconAnchor: [12, 41] });

interface StationFormDialogProps {
  open: boolean;
  companyId: string;
  station: Station | null;
  onClose: () => void;
  onSuccess: (station: Station, mode: 'created' | 'updated') => void;
}

type StationForm = Omit<StationPayload, 'opening_time_local' | 'closing_time_local'> & {
  opening_time_local: string;
  closing_time_local: string;
};

const emptyForm: StationForm = {
  name: '',
  price_per_kwh: 12,
  minimum_session_fee: 0,
  timezone: 'Asia/Kolkata',
  opening_time_local: '',
  closing_time_local: '',
  locked_gate: false,
  lat: 12.9716,
  lng: 77.5946,
};

function LocationMarker({ position, onChange }: { position: [number, number]; onChange: (position: [number, number]) => void }) {
  useMapEvents({ click: (event) => onChange([event.latlng.lat, event.latlng.lng]) });
  return <Marker position={position} icon={markerIcon} />;
}

export function StationFormDialog({ open, companyId, station, onClose, onSuccess }: StationFormDialogProps) {
  const [form, setForm] = useState<StationForm>(emptyForm);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isEditing = Boolean(station);

  useEffect(() => {
    if (!open) return;
    setError('');
    setForm(station ? {
      name: station.name,
      price_per_kwh: Number(station.price_per_kwh),
      minimum_session_fee: Number(station.minimum_session_fee),
      timezone: station.timezone,
      opening_time_local: station.opening_time_local?.slice(0, 5) ?? '',
      closing_time_local: station.closing_time_local?.slice(0, 5) ?? '',
      locked_gate: station.locked_gate,
      lat: station.lat,
      lng: station.lng,
    } : emptyForm);
  }, [open, station]);

  const setField = <K extends keyof StationForm>(key: K, value: StationForm[K]) => setForm((current) => ({ ...current, [key]: value }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (form.opening_time_local && !form.closing_time_local || !form.opening_time_local && form.closing_time_local) {
      setError('Set both opening and closing times, or leave both empty for 24-hour operation.');
      return;
    }
    setIsSubmitting(true);
    try {
      const payload: StationPayload = {
        ...form,
        opening_time_local: form.opening_time_local || null,
        closing_time_local: form.closing_time_local || null,
      };
      const result = station
        ? await operatorService.updateStation(station.station_id, payload)
        : await operatorService.createStation(companyId, payload);
      onSuccess(result, station ? 'updated' : 'created');
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'The station could not be saved.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEditing ? 'Edit station' : 'Create station'}
      description="Set pricing, operating hours, and the exact map location."
      size="lg"
      preventClose={isSubmitting}
      footer={<><Button onClick={onClose} disabled={isSubmitting}>Cancel</Button><Button type="submit" form="station-form" variant="primary" isLoading={isSubmitting}>{isEditing ? 'Save station' : 'Create station'}</Button></>}
    >
      <form id="station-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        {error && <Alert tone="error" title="Couldn’t save the station">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Station name" className="sm:col-span-2">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={form.name} onChange={(event) => setField('name', event.target.value)} placeholder="Indiranagar Charge Hub" required />}</Field>
          <Field label="Price per kWh">{({ id, describedBy, invalid }) => <div className="relative"><span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 font-bold text-[var(--steel)]">₹</span><input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control pl-8" type="number" min={0} step="0.01" value={form.price_per_kwh} onChange={(event) => setField('price_per_kwh', Number(event.target.value))} required /></div>}</Field>
          <Field label="Minimum session fee">{({ id, describedBy, invalid }) => <div className="relative"><span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 font-bold text-[var(--steel)]">₹</span><input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control pl-8" type="number" min={0} step="0.01" value={form.minimum_session_fee} onChange={(event) => setField('minimum_session_fee', Number(event.target.value))} required /></div>}</Field>
          <Field label="Timezone">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control font-data" value={form.timezone} onChange={(event) => setField('timezone', event.target.value)} placeholder="Asia/Kolkata" required />}</Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Opens" optional>{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" type="time" value={form.opening_time_local} onChange={(event) => setField('opening_time_local', event.target.value)} />}</Field>
            <Field label="Closes" optional>{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" type="time" value={form.closing_time_local} onChange={(event) => setField('closing_time_local', event.target.value)} />}</Field>
          </div>
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border border-[var(--line)] p-4"><input type="checkbox" checked={form.locked_gate} onChange={(event) => setField('locked_gate', event.target.checked)} className="mt-1 size-4 accent-[var(--teal)]" /><span><span className="block text-sm font-bold">Locked gate or restricted access</span><span className="mt-0.5 block text-xs text-[var(--steel)]">Drivers will see an access warning on the station page.</span></span></label>

        <div>
          <p className="field-label mb-2">Map location</p>
          <div className="mb-3 grid grid-cols-2 gap-3">
            <Field label="Latitude">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control font-data" type="number" step="any" value={form.lat} onChange={(event) => setField('lat', Number(event.target.value))} required />}</Field>
            <Field label="Longitude">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control font-data" type="number" step="any" value={form.lng} onChange={(event) => setField('lng', Number(event.target.value))} required />}</Field>
          </div>
          <div className="h-64 overflow-hidden rounded-[var(--radius-md)] border border-[var(--line)]" aria-label="Click the map to place the station marker">
            <MapContainer center={[form.lat, form.lng]} zoom={13} className="h-full w-full"><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" /><LocationMarker position={[form.lat, form.lng]} onChange={(position) => setForm((current) => ({ ...current, lat: position[0], lng: position[1] }))} /></MapContainer>
          </div>
          <p className="mt-2 text-xs text-[var(--steel)]">Click the map or enter precise coordinates.</p>
        </div>
      </form>
    </Dialog>
  );
}
