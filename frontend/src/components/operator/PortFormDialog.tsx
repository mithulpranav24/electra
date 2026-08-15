import { useEffect, useState } from 'react';
import type { ChargingPort, Station } from '../../types';
import { operatorService, type PortPayload } from '../../services/api';
import { getErrorMessage } from '../../lib/errors';
import { Alert } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { Button } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';

interface PortFormDialogProps {
  open: boolean;
  stations: Station[];
  stationId: string;
  port: ChargingPort | null;
  onClose: () => void;
  onSuccess: (port: ChargingPort, mode: 'created' | 'updated') => void;
}

const emptyPort: PortPayload = { qr_code: '', connector_type: 'CCS2', charger_type: 'DC Fast', status: 'Available' };

export function PortFormDialog({ open, stations, stationId, port, onClose, onSuccess }: PortFormDialogProps) {
  const [targetStationId, setTargetStationId] = useState('');
  const [form, setForm] = useState<PortPayload>(emptyPort);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isEditing = Boolean(port);

  useEffect(() => {
    if (!open) return;
    setError('');
    setTargetStationId(stationId || stations[0]?.station_id || '');
    setForm(port ? {
      qr_code: port.qr_code,
      connector_type: port.connector_type,
      charger_type: port.charger_type,
      status: port.status,
      is_pending_maintenance: port.is_pending_maintenance,
      has_health_warning: port.has_health_warning,
      has_blocked_warning: port.has_blocked_warning,
      is_active: port.is_active,
    } : emptyPort);
  }, [open, port, stationId, stations]);

  const setField = <K extends keyof PortPayload>(key: K, value: PortPayload[K]) => setForm((current) => ({ ...current, [key]: value }));

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!port && !targetStationId) { setError('Select a station for this port.'); return; }
    setError('');
    setIsSubmitting(true);
    try {
      const result = port ? await operatorService.updatePort(port.port_id, form) : await operatorService.createPort(targetStationId, form);
      onSuccess(result, port ? 'updated' : 'created');
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'The charging port could not be saved.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title={isEditing ? 'Edit charging port' : 'Add charging port'} description="Keep physical connector, QR, and operating state aligned." size="md" preventClose={isSubmitting} footer={<><Button onClick={onClose} disabled={isSubmitting}>Cancel</Button><Button type="submit" form="port-form" variant="primary" isLoading={isSubmitting}>{isEditing ? 'Save port' : 'Add port'}</Button></>}>
      <form id="port-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        {error && <Alert tone="error" title="Couldn’t save the port">{error}</Alert>}
        {!isEditing && <Field label="Station">{({ id, describedBy, invalid }) => <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={targetStationId} onChange={(event) => setTargetStationId(event.target.value)} required><option value="">Select station</option>{stations.filter((station) => station.is_active).map((station) => <option key={station.station_id} value={station.station_id}>{station.name}</option>)}</select>}</Field>}
        <Field label="QR code" hint="Must be unique across ports.">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control font-data" value={form.qr_code} onChange={(event) => setField('qr_code', event.target.value)} required />}</Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Connector type">{({ id, describedBy, invalid }) => <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={form.connector_type} onChange={(event) => setField('connector_type', event.target.value)}><option value="CCS2">CCS 2</option><option value="CCS1">CCS 1</option><option value="CHAdeMO">CHAdeMO</option><option value="Type 2">Type 2</option></select>}</Field>
          <Field label="Charger type">{({ id, describedBy, invalid }) => <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={form.charger_type} onChange={(event) => setField('charger_type', event.target.value)}><option value="DC Fast">DC Fast</option><option value="AC Level 2">AC Level 2</option><option value="Ultra Fast DC">Ultra Fast DC</option></select>}</Field>
        </div>
        {isEditing && (
          <>
            <Field label="Operational status" hint="Reserved and Charging states are controlled by live charging workflows.">{({ id, describedBy, invalid }) => <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={form.status} onChange={(event) => setField('status', event.target.value)} disabled={port?.status === 'Reserved' || port?.status === 'Charging'}><option value="Available">Available</option><option value="Maintenance">Maintenance</option><option value="Offline">Offline</option>{port && !['Available', 'Maintenance', 'Offline'].includes(port.status) && <option value={port.status}>{port.status}</option>}</select>}</Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border border-[var(--line)] p-3"><input type="checkbox" className="mt-1 size-4 accent-[var(--teal)]" checked={form.has_health_warning ?? false} onChange={(event) => setField('has_health_warning', event.target.checked)} /><span><span className="block text-sm font-bold">Health warning</span><span className="text-xs text-[var(--steel)]">Reported charger fault</span></span></label>
              <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border border-[var(--line)] p-3"><input type="checkbox" className="mt-1 size-4 accent-[var(--teal)]" checked={form.has_blocked_warning ?? false} onChange={(event) => setField('has_blocked_warning', event.target.checked)} /><span><span className="block text-sm font-bold">Blocked bay warning</span><span className="text-xs text-[var(--steel)]">Vehicle access issue</span></span></label>
              <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-md)] border border-[var(--line)] p-3 sm:col-span-2"><input type="checkbox" className="mt-1 size-4 accent-[var(--teal)]" checked={form.is_pending_maintenance ?? false} onChange={(event) => setField('is_pending_maintenance', event.target.checked)} /><span><span className="block text-sm font-bold">Pending maintenance</span><span className="text-xs text-[var(--steel)]">Blocks new reservation assignment while work is planned.</span></span></label>
            </div>
          </>
        )}
      </form>
    </Dialog>
  );
}
