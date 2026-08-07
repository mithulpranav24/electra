import { useState, useEffect } from 'react';
import type { Vehicle } from '../types';
import { vehicleService } from '../services/api';
import { X, Save, AlertCircle } from 'lucide-react';

interface VehicleFormModalProps {
  vehicle: Vehicle | null;
  onClose: () => void;
  onSuccess: () => void;
}

const VehicleFormModal: React.FC<VehicleFormModalProps> = ({ vehicle, onClose, onSuccess }) => {
  const [formData, setFormData] = useState<{
    make: string;
    model: string;
    license_plate: string;
    battery_capacity_kwh: number;
    connector_type: 'Type2' | 'CCS2' | 'CHAdeMO';
  }>({
    make: '',
    model: '',
    license_plate: '',
    battery_capacity_kwh: 50,
    connector_type: 'Type2'
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const isEditing = !!vehicle;

  useEffect(() => {
    if (vehicle) {
      setFormData({
        make: vehicle.make,
        model: vehicle.model,
        license_plate: vehicle.license_plate,
        battery_capacity_kwh: vehicle.battery_capacity_kwh,
        connector_type: vehicle.connector_type
      });
    }
  }, [vehicle]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? Number(value) : value
    }) as typeof formData);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      if (isEditing && vehicle) {
        await vehicleService.updateVehicle(vehicle.id, formData);
      } else {
        await vehicleService.createVehicle(formData);
      }
      onSuccess();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to save vehicle');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="skeuo-panel w-full max-w-md animate-in fade-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-6 border-b border-white/10">
          <h2 className="text-2xl font-bold">{isEditing ? 'Edit Vehicle' : 'Add New Vehicle'}</h2>
          <button 
            onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center bg-skeuo-base shadow-skeuo active:shadow-skeuo-pressed text-skeuo-text-muted hover:text-red-500"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5">
          {error && (
            <div className="bg-red-50 text-red-600 p-3 rounded-xl border border-red-200 flex items-center gap-2 text-sm font-medium">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Make</label>
              <input
                type="text"
                name="make"
                value={formData.make}
                onChange={handleChange}
                required
                className="skeuo-input"
                placeholder="e.g. Tesla"
              />
            </div>
            
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Model</label>
              <input
                type="text"
                name="model"
                value={formData.model}
                onChange={handleChange}
                required
                className="skeuo-input"
                placeholder="e.g. Model 3"
              />
            </div>
          </div>

          <div className="skeuo-text-field-group">
            <label className="skeuo-label">License Plate</label>
            <input
              type="text"
              name="license_plate"
              value={formData.license_plate}
              onChange={handleChange}
              required
              className="skeuo-input uppercase"
              placeholder="e.g. MH 12 AB 1234"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Battery (kWh)</label>
              <div className="relative">
                <input
                  type="number"
                  name="battery_capacity_kwh"
                  value={formData.battery_capacity_kwh}
                  onChange={handleChange}
                  required
                  min="10"
                  max="200"
                  step="0.1"
                  className="skeuo-input w-full pr-12"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-skeuo-text-muted text-sm font-semibold">kWh</span>
              </div>
            </div>

            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Connector</label>
              <select
                name="connector_type"
                value={formData.connector_type}
                onChange={handleChange}
                required
                className="skeuo-input cursor-pointer"
              >
                <option value="Type2">Type 2</option>
                <option value="CCS2">CCS 2</option>
                <option value="CHAdeMO">CHAdeMO</option>
              </select>
            </div>
          </div>

          <div className="flex gap-4 mt-4 pt-4 border-t border-white/10">
            <button 
              type="button" 
              onClick={onClose} 
              className="skeuo-btn flex-1 bg-skeuo-base"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button 
              type="submit" 
              className="skeuo-btn skeuo-btn-primary flex-1"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <Save size={18} />
                  <span>{isEditing ? 'Save Changes' : 'Add Vehicle'}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default VehicleFormModal;
