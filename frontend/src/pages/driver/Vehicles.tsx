import { useState, useEffect } from 'react';
import type { Vehicle } from '../../types';
import { vehicleService } from '../../services/api';
import VehicleCard from '../../components/VehicleCard';
import VehicleFormModal from '../../components/VehicleFormModal';
import { Plus, Car as CarIcon, AlertCircle } from 'lucide-react';

const Vehicles = () => {
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);

  const fetchVehicles = async () => {
    try {
      setIsLoading(true);
      const data = await vehicleService.getVehicles();
      setVehicles(data);
    } catch (err) {
      setError('Failed to load vehicles');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchVehicles();
  }, []);

  const handleAddClick = () => {
    setEditingVehicle(null);
    setIsModalOpen(true);
  };

  const handleEditClick = (vehicle: Vehicle) => {
    setEditingVehicle(vehicle);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this vehicle?')) return;
    try {
      await vehicleService.deleteVehicle(id);
      await fetchVehicles();
    } catch (err) {
      alert('Failed to delete vehicle');
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await vehicleService.setDefaultVehicle(id);
      await fetchVehicles();
    } catch (err) {
      alert('Failed to set default vehicle');
    }
  };

  const handleModalSuccess = () => {
    setIsModalOpen(false);
    fetchVehicles();
  };

  return (
    <div className="max-w-6xl mx-auto flex flex-col gap-6 h-full">
      <header className="flex justify-between items-end bg-skeuo-base skeuo-panel p-6 shadow-sm border border-white/40">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-3">
            <div className="p-2 bg-skeuo-dark rounded-xl shadow-skeuo-pressed">
              <CarIcon size={24} className="text-skeuo-accent" />
            </div>
            My Vehicles
          </h1>
          <p className="text-skeuo-text-muted mt-2">Manage your EVs, battery capacities, and connector types for accurate charging estimates.</p>
        </div>
        <button onClick={handleAddClick} className="skeuo-btn skeuo-btn-primary h-12">
          <Plus size={20} />
          <span>Add Vehicle</span>
        </button>
      </header>

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-xl border border-red-200 flex items-center gap-2">
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex-1 flex justify-center items-center">
          <div className="animate-pulse flex flex-col items-center gap-4">
            <div className="w-12 h-12 rounded-full border-4 border-skeuo-accent border-t-transparent animate-spin"></div>
            <p className="text-skeuo-text-muted font-semibold">Loading vehicles...</p>
          </div>
        </div>
      ) : vehicles.length === 0 ? (
        <div className="flex-1 flex flex-col justify-center items-center skeuo-panel p-12 text-center opacity-80 border-dashed border-2 border-skeuo-text-muted/30">
          <div className="w-20 h-20 bg-skeuo-dark rounded-full shadow-skeuo-pressed flex items-center justify-center mb-6">
            <CarIcon size={40} className="text-skeuo-text-muted" />
          </div>
          <h2 className="text-2xl font-bold mb-2">No vehicles found</h2>
          <p className="text-skeuo-text-muted mb-6 max-w-md">You haven't added any vehicles yet. Add your EV to get started with reservations and charging.</p>
          <button onClick={handleAddClick} className="skeuo-btn skeuo-btn-primary">
            <Plus size={20} />
            <span>Add Your First Vehicle</span>
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {vehicles.map(vehicle => (
            <VehicleCard 
              key={vehicle.id} 
              vehicle={vehicle} 
              onEdit={() => handleEditClick(vehicle)}
              onDelete={() => handleDelete(vehicle.id)}
              onSetDefault={() => handleSetDefault(vehicle.id)}
            />
          ))}
        </div>
      )}

      {isModalOpen && (
        <VehicleFormModal 
          vehicle={editingVehicle} 
          onClose={() => setIsModalOpen(false)}
          onSuccess={handleModalSuccess}
        />
      )}
    </div>
  );
};

export default Vehicles;
