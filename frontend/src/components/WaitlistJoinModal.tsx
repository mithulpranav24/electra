import { Link } from 'react-router-dom';
import { Clock3, MapPin, ShieldCheck } from 'lucide-react';
import type { Vehicle } from '../types';
import { formatCurrency, vehicleId } from '../lib/format';
import { Alert } from '../ui/Feedback';
import { Button } from '../ui/Button';
import { Dialog } from '../ui/Dialog';
import { Field } from '../ui/Field';

interface WaitlistJoinModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  stationName: string;
  minimumSessionFee: number;
  vehicles: Vehicle[];
  selectedVehicleId: string;
  onVehicleChange: (id: string) => void;
  walletBalance: number;
  isLoading?: boolean;
}

export function WaitlistJoinModal({ open, onClose, onConfirm, stationName, minimumSessionFee, vehicles, selectedVehicleId, onVehicleChange, walletBalance, isLoading = false }: WaitlistJoinModalProps) {
  const requiredBalance = 1000 + Number(minimumSessionFee || 0);
  const hasFunds = walletBalance >= requiredBalance;
  const canJoin = Boolean(selectedVehicleId && hasFunds);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Join the waitlist"
      description={stationName}
      size="md"
      preventClose={isLoading}
      footer={<><Button onClick={onClose} disabled={isLoading}>Not now</Button><Button variant="primary" onClick={onConfirm} isLoading={isLoading} disabled={!canJoin}>Join waitlist</Button></>}
    >
      <div className="flex flex-col gap-5">
        {vehicles.length === 0 ? (
          <Alert tone="warning" title="No compatible vehicle">
            Add a vehicle before joining a waitlist. <Link to="/driver/vehicles" className="font-bold underline">Go to vehicles</Link>
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
            Joining a waitlist requires ₹1,000 escrow plus this station's ₹{minimumSessionFee} minimum session fee ({formatCurrency(requiredBalance)} total). Your current balance is {formatCurrency(walletBalance)}. <Link to="/driver/wallet" className="font-bold underline">Top up wallet</Link>
          </Alert>
        )}

        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="surface-muted p-4">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]"><MapPin size={15} /> Proximity</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">2 km</dd>
          </div>
          <div className="surface-muted p-4">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]"><Clock3 size={15} /> Offer window</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">90 sec</dd>
          </div>
          <div className="surface-muted p-4">
            <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel)]"><ShieldCheck size={15} /> Locked-in tariff</dt>
            <dd className="font-data mt-1.5 text-lg font-bold">Today's rate</dd>
          </div>
        </dl>

        <p className="text-sm leading-6 text-[var(--steel-dark)]">
          You must be within 2km of the station to join its waitlist. When a compatible port frees up, you'll have 90 seconds to confirm before it passes to the next driver in line. You can hold only one waitlist entry at a time.
        </p>
      </div>
    </Dialog>
  );
}
