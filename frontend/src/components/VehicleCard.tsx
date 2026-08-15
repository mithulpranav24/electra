import { BatteryMedium, Check, Pencil, PlugZap, Trash2 } from 'lucide-react';
import type { Vehicle } from '../types';
import { Button, IconButton } from '../ui/Button';
import { Badge } from '../ui/Badge';

interface VehicleCardProps {
  vehicle: Vehicle;
  onEdit: () => void;
  onDelete: () => void;
  onSetDefault: () => void;
  isUpdatingDefault?: boolean;
}

export default function VehicleCard({ vehicle, onEdit, onDelete, onSetDefault, isUpdatingDefault = false }: VehicleCardProps) {
  const vehicleName = [vehicle.make, vehicle.model].filter(Boolean).join(' ') || 'Unnamed vehicle';

  return (
    <article className={`surface flex min-h-64 flex-col overflow-hidden ${vehicle.is_default ? 'border-[var(--teal)]' : ''}`}>
      <div className="flex items-start justify-between gap-3 border-b border-[var(--line)] p-5">
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <h2 className="font-display truncate text-xl font-bold tracking-tight">{vehicleName}</h2>
            {vehicle.is_default && <Badge tone="success">Default</Badge>}
          </div>
          <p className="font-data inline-flex rounded-md bg-[var(--paper-muted)] px-2.5 py-1 text-xs font-bold uppercase tracking-[0.08em] text-[var(--steel-dark)]">
            {vehicle.license_plate}
          </p>
        </div>
        <div className="flex gap-1">
          <IconButton label={`Edit ${vehicleName}`} onClick={onEdit}><Pencil size={17} /></IconButton>
          <IconButton label={`Delete ${vehicleName}`} variant="danger" onClick={onDelete}><Trash2 size={17} /></IconButton>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-px bg-[var(--line)]">
        <div className="bg-white p-4">
          <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.1em] text-[var(--steel)]"><BatteryMedium size={15} /> Battery</dt>
          <dd className="font-data mt-1 text-lg font-bold">{vehicle.battery_capacity_kwh} kWh</dd>
        </div>
        <div className="bg-white p-4">
          <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.1em] text-[var(--steel)]"><PlugZap size={15} /> Connector</dt>
          <dd className="font-data mt-1 text-lg font-bold">{vehicle.connector_type === 'Type2' ? 'Type 2' : vehicle.connector_type}</dd>
        </div>
      </dl>

      <div className="mt-auto flex items-center justify-between gap-3 p-4">
        <p className="text-xs text-[var(--steel)]">Used to match compatible charging ports.</p>
        {!vehicle.is_default && (
          <Button size="sm" variant="ghost" icon={<Check size={16} />} onClick={onSetDefault} isLoading={isUpdatingDefault}>Make default</Button>
        )}
      </div>
    </article>
  );
}
