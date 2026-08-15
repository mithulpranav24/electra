import { useCallback, useEffect, useState } from 'react';
import { Car, Plus } from 'lucide-react';
import type { Vehicle } from '../../types';
import { vehicleService } from '../../services/api';
import { getErrorMessage } from '../../lib/errors';
import { vehicleId } from '../../lib/format';
import VehicleCard from '../../components/VehicleCard';
import VehicleFormModal from '../../components/VehicleFormModal';
import { Button } from '../../ui/Button';
import { ConfirmDialog } from '../../ui/ConfirmDialog';
import { EmptyState, ErrorState, Skeleton } from '../../ui/Feedback';
import { PageHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';

export default function Vehicles() {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);
  const [deletingVehicle, setDeletingVehicle] = useState<Vehicle | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [defaultPendingId, setDefaultPendingId] = useState('');
  const { pushToast } = useToast();

  const loadVehicles = useCallback(async (showLoader = true) => {
    if (showLoader) setIsLoading(true);
    setError('');
    try {
      setVehicles(await vehicleService.getVehicles());
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Your vehicles could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void loadVehicles(); }, [loadVehicles]);

  const openCreate = () => {
    setEditingVehicle(null);
    setFormOpen(true);
  };

  const handleSetDefault = async (vehicle: Vehicle) => {
    const id = vehicleId(vehicle);
    const previous = vehicles;
    setDefaultPendingId(id);
    setVehicles((items) => items.map((item) => ({ ...item, is_default: vehicleId(item) === id })));
    try {
      await vehicleService.setDefaultVehicle(id);
      await loadVehicles(false);
      pushToast({ title: 'Default vehicle updated', message: `${[vehicle.make, vehicle.model].filter(Boolean).join(' ') || vehicle.license_plate} will be preselected for compatible reservations.`, tone: 'success' });
    } catch (updateError) {
      setVehicles(previous);
      pushToast({ title: 'Couldn’t update the default vehicle', message: getErrorMessage(updateError, 'Try again.'), tone: 'error' });
    } finally {
      setDefaultPendingId('');
    }
  };

  const handleDelete = async () => {
    if (!deletingVehicle) return;
    setIsDeleting(true);
    try {
      await vehicleService.deleteVehicle(vehicleId(deletingVehicle));
      setDeletingVehicle(null);
      await loadVehicles(false);
      pushToast({ title: 'Vehicle removed', message: 'The vehicle is no longer available for new reservations.', tone: 'success' });
    } catch (deleteError) {
      pushToast({ title: 'Couldn’t remove the vehicle', message: getErrorMessage(deleteError, 'It may be linked to an active reservation or charging session.'), tone: 'error' });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Garage" title="Vehicles" description="Keep connector and battery details accurate so every charger result is relevant." actions={<Button variant="primary" size="lg" icon={<Plus size={19} />} onClick={openCreate}>Add vehicle</Button>} />

      {isLoading ? (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3" aria-label="Loading vehicles">
          {Array.from({ length: 3 }).map((_, index) => <div key={index} className="surface p-5"><Skeleton className="h-6 w-3/5" /><Skeleton className="mt-3 h-5 w-28" /><div className="mt-8 grid grid-cols-2 gap-3"><Skeleton className="h-16" /><Skeleton className="h-16" /></div></div>)}
        </div>
      ) : error ? (
        <ErrorState description={error} onRetry={() => void loadVehicles()} />
      ) : vehicles.length === 0 ? (
        <div className="surface">
          <EmptyState title="Add your first vehicle" description="Electra uses your connector type to identify compatible ports and your battery size for accurate charging estimates." icon={<Car size={24} />} action={<Button variant="primary" icon={<Plus size={18} />} onClick={openCreate}>Add vehicle</Button>} />
        </div>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {vehicles.map((vehicle) => (
            <VehicleCard
              key={vehicleId(vehicle)}
              vehicle={vehicle}
              onEdit={() => { setEditingVehicle(vehicle); setFormOpen(true); }}
              onDelete={() => setDeletingVehicle(vehicle)}
              onSetDefault={() => void handleSetDefault(vehicle)}
              isUpdatingDefault={defaultPendingId === vehicleId(vehicle)}
            />
          ))}
        </div>
      )}

      <VehicleFormModal
        open={formOpen}
        vehicle={editingVehicle}
        onClose={() => setFormOpen(false)}
        onSuccess={(_vehicle, mode) => {
          setFormOpen(false);
          void loadVehicles(false);
          pushToast({ title: mode === 'created' ? 'Vehicle added' : 'Vehicle updated', message: 'Your charging matches will use the latest details.', tone: 'success' });
        }}
      />

      <ConfirmDialog
        open={Boolean(deletingVehicle)}
        onClose={() => setDeletingVehicle(null)}
        onConfirm={() => void handleDelete()}
        title="Remove this vehicle?"
        description={<><strong>{deletingVehicle ? [deletingVehicle.make, deletingVehicle.model].filter(Boolean).join(' ') || deletingVehicle.license_plate : 'This vehicle'}</strong> will no longer be available for new reservations. The server will block removal if it is tied to active charging.</>}
        confirmLabel="Remove vehicle"
        isLoading={isDeleting}
      />
    </div>
  );
}
