import { useEffect, useState } from 'react';
import type { ConnectorType, Vehicle } from '../types';
import { vehicleService, type VehiclePayload } from '../services/api';
import { getErrorMessage } from '../lib/errors';
import { vehicleId } from '../lib/format';
import { Alert } from '../ui/Feedback';
import { Field } from '../ui/Field';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';

interface VehicleFormModalProps {
  open: boolean;
  vehicle: Vehicle | null;
  onClose: () => void;
  onSuccess: (vehicle: Vehicle, mode: 'created' | 'updated') => void;
}

const emptyForm: VehiclePayload = {
  make: '',
  model: '',
  license_plate: '',
  battery_capacity_kwh: 50,
  connector_type: 'Type2',
};

export default function VehicleFormModal({ open, vehicle, onClose, onSuccess }: VehicleFormModalProps) {
  const [formData, setFormData] = useState<VehiclePayload>(emptyForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const isEditing = Boolean(vehicle);

  useEffect(() => {
    if (!open) return;
    setError('');
    setFormData(vehicle ? {
      make: vehicle.make ?? '',
      model: vehicle.model ?? '',
      license_plate: vehicle.license_plate,
      battery_capacity_kwh: vehicle.battery_capacity_kwh,
      connector_type: (vehicle.connector_type === 'Type 2' ? 'Type2' : vehicle.connector_type) as ConnectorType,
    } : emptyForm);
  }, [open, vehicle]);

  const setField = <K extends keyof VehiclePayload>(key: K, value: VehiclePayload[K]) => {
    setFormData((current) => ({ ...current, [key]: value }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const normalized = { ...formData, license_plate: formData.license_plate.trim().toUpperCase() };
      const result = vehicle
        ? await vehicleService.updateVehicle(vehicleId(vehicle), normalized)
        : await vehicleService.createVehicle(normalized);
      onSuccess(result, vehicle ? 'updated' : 'created');
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'The vehicle could not be saved.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEditing ? 'Edit vehicle' : 'Add a vehicle'}
      description="Vehicle details are used to show compatible charging ports."
      preventClose={isSubmitting}
      footer={<><Button onClick={onClose} disabled={isSubmitting}>Cancel</Button><Button type="submit" form="vehicle-form" variant="primary" isLoading={isSubmitting}>{isEditing ? 'Save changes' : 'Add vehicle'}</Button></>}
    >
      <form id="vehicle-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        {error && <Alert tone="error" title="Couldn’t save the vehicle">{error}</Alert>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Make" optional>
            {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={formData.make ?? ''} onChange={(event) => setField('make', event.target.value)} placeholder="Tata" />}
          </Field>
          <Field label="Model" optional>
            {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={formData.model ?? ''} onChange={(event) => setField('model', event.target.value)} placeholder="Nexon EV" />}
          </Field>
        </div>
        <Field label="Registration number">
          {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control font-data uppercase" value={formData.license_plate} onChange={(event) => setField('license_plate', event.target.value)} placeholder="KA 01 AB 1234" maxLength={50} required />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Battery capacity" hint="Accepted range: 2–250 kWh.">
            {({ id, describedBy, invalid }) => <div className="relative"><input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control pr-14" type="number" min={2} max={250} step="0.1" value={formData.battery_capacity_kwh} onChange={(event) => setField('battery_capacity_kwh', Number(event.target.value))} required /><span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm font-bold text-[var(--steel)]">kWh</span></div>}
          </Field>
          <Field label="Connector">
            {({ id, describedBy, invalid }) => (
              <select id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={formData.connector_type} onChange={(event) => setField('connector_type', event.target.value as ConnectorType)} required>
                <option value="Type2">Type 2</option>
                <option value="CCS2">CCS 2</option>
                <option value="CHAdeMO">CHAdeMO</option>
              </select>
            )}
          </Field>
        </div>
      </form>
    </Dialog>
  );
}
