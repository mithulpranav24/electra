import type { Vehicle } from '../types';
import { Battery, Zap, Edit2, Trash2, CheckCircle2 } from 'lucide-react';

interface VehicleCardProps {
  vehicle: Vehicle;
  onEdit: () => void;
  onDelete: () => void;
  onSetDefault: () => void;
}

const VehicleCard: React.FC<VehicleCardProps> = ({ vehicle, onEdit, onDelete, onSetDefault }) => {
  return (
    <div className={`skeuo-panel p-5 flex flex-col gap-4 relative overflow-hidden transition-all hover:scale-[1.01] ${vehicle.is_default ? 'ring-2 ring-skeuo-accent border-transparent' : ''}`}>
      {vehicle.is_default && (
        <div className="absolute top-0 right-0 bg-skeuo-accent text-white text-[10px] uppercase font-bold tracking-wider px-3 py-1 rounded-bl-xl shadow-sm">
          Default
        </div>
      )}
      
      <div className="flex justify-between items-start mt-2">
        <div>
          <h3 className="text-xl font-bold truncate pr-16">{vehicle.make} {vehicle.model}</h3>
          <p className="text-sm font-mono text-skeuo-text-muted mt-1 bg-white/20 dark:bg-black/20 inline-block px-2 py-0.5 rounded border border-white/10 shadow-skeuo-pressed-sm">{vehicle.license_plate}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-2">
        <div className="flex items-center gap-2 bg-skeuo-base shadow-skeuo-pressed-sm rounded-lg p-2 border border-white/10">
          <Battery size={16} className="text-emerald-500" />
          <div className="flex flex-col">
             <span className="text-[10px] text-skeuo-text-muted uppercase font-semibold">Capacity</span>
             <span className="font-bold text-sm leading-none">{vehicle.battery_capacity_kwh} kWh</span>
          </div>
        </div>
        
        <div className="flex items-center gap-2 bg-skeuo-base shadow-skeuo-pressed-sm rounded-lg p-2 border border-white/10">
          <Zap size={16} className="text-blue-500" />
          <div className="flex flex-col">
             <span className="text-[10px] text-skeuo-text-muted uppercase font-semibold">Connector</span>
             <span className="font-bold text-sm leading-none">{vehicle.connector_type}</span>
          </div>
        </div>
      </div>

      <div className="flex justify-between items-center pt-3 border-t border-white/20 mt-auto">
        <div className="flex gap-2">
           <button 
             onClick={onEdit}
             className="w-8 h-8 rounded-full bg-skeuo-base shadow-skeuo border border-white/40 flex items-center justify-center text-skeuo-text hover:text-blue-500 active:shadow-skeuo-pressed transition-all"
             title="Edit Vehicle"
           >
             <Edit2 size={14} />
           </button>
           <button 
             onClick={onDelete}
             className="w-8 h-8 rounded-full bg-skeuo-base shadow-skeuo border border-white/40 flex items-center justify-center text-skeuo-text hover:text-red-500 active:shadow-skeuo-pressed transition-all"
             title="Delete Vehicle"
           >
             <Trash2 size={14} />
           </button>
        </div>
        
        {!vehicle.is_default && (
          <button 
            onClick={onSetDefault}
            className="text-xs font-semibold flex items-center gap-1 text-skeuo-text-muted hover:text-skeuo-accent transition-colors"
          >
            <CheckCircle2 size={14} />
            Set Default
          </button>
        )}
      </div>
    </div>
  );
};

export default VehicleCard;
