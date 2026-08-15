import { Link } from 'react-router-dom';
import { Clock3, ShieldCheck, WalletCards } from 'lucide-react';
import type { ChargingPort, Vehicle } from '../types';
import { formatCurrency, vehicleId } from '../lib/format';
import { Alert } from '../ui/Feedback';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';

interface ReservationModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  stationName: string;
  port: ChargingPort | null;
  pricePerKwh: number;
  vehicles: Vehicle[];
  selectedVehicleId: string;
  onVehicleChange: (id: string) => void;
  walletBalance: number;
  isLoading?: boolean;
}

export function ReservationModal({ open, onClose, onConfirm, stationName, port, pricePerKwh, vehicles, selectedVehicleId, onVehicleChange, walletBalance, isLoading = false }: ReservationModalProps) {
  const hasFunds = walletBalance >= 1000;
  const canReserve = Boolean(port && selectedVehicleId && hasFunds);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Review reservation"
      description={port ? `${stationName} · ${port.connector_type} · ${port.charger_type}` : stationName}
      size="md"
      preventClose={isLoading}
      footer={<><Button onClick={onClose} disabled={isLoading}>Not now</Button><Button variant="primary" onClick={onConfirm} isLoading={isLoading} disabled={!canReserve}>Reserve this port</Button></>}
    >
      <div className="flex flex-col gap-5">
        {vehicles.length === 0 ? (
          <Alert tone="warning" title="No compatible vehicle">
            Add a vehicle with the same connector before reserving. <Link to="/driver/vehicles" className="font-bold underline">Go to vehicles</Link>
          </Alert>
        ) : (
          <Field label="Vehicle">
            {({ id, describedBy }) => (
              <select id={id} aria-describedby={describedBy} className="field-control" value={selectedVehicleId} onChange={(event) => onVehicleChange(event.target.value)} required>
                {vehicles.map((vehicle) => <option key={vehicleId(vehicle)} value={vehicleId(vehicle)}>{[vehicle.make, vehicle.model].filter(Boolean).join(' ') || vehicle.license_plate} · {vehicle.license_plate}{vehicle.is_default ? ' (default)' : ''}</option>)}
              </select>
            )}
          </Field>
        )}

        {!hasFunds && (
          <Alert tone="error" title="Wallet balance is too low">
            Reservations require a ₹1,000 escrow. Your current balance is {formatCurrency(walletBalance)}. <Link to="/driver/wallet" className="font-bold underline">Top up wallet</Link>
          </Alert>
        )}

        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="surface-muted p-4">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]"><WalletCards size={15} /> Escrow hold</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">₹1,000</dd>
          </div>
          <div className="surface-muted p-4">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]"><Clock3 size={15} /> Arrival window</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">15 min</dd>
          </div>
          <div className="surface-muted p-4">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]"><ShieldCheck size={15} /> Tariff</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">{formatCurrency(pricePerKwh)}/kWh</dd>
          </div>
        </dl>

        <p className="text-sm leading-6 text-[var(--steel-dark)]">
          The escrow is held when the reservation is confirmed. Arrive and plug in within 15 minutes; otherwise the reservation expires and the escrow may be forfeited. Cancellation refunds depend on timing and your recent cancellation history.
        </p>
      </div>
    </Dialog>
  );
}
