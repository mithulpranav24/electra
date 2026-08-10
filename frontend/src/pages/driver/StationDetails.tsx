import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../../services/api';
import { MapPin, Zap, Clock, AlertTriangle, ArrowLeft } from 'lucide-react';
import { ReservationModal } from '../../components/ReservationModal';

export const StationDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [station, setStation] = useState<any>(null);
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [selectedPort, setSelectedPort] = useState<any>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [reserving, setReserving] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stationRes, vehiclesRes] = await Promise.all([
          api.get(`/search/stations/${id}`),
          api.get('/vehicles')
        ]);
        
        if (stationRes.data.success) {
          setStation(stationRes.data.data);
        } else {
          setError('Failed to fetch station');
        }
        
        if (vehiclesRes.data.success) {
          setVehicles(vehiclesRes.data.data);
        }
      } catch (err: any) {
        setError('Failed to load details');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [id]);

  const handleReserve = async () => {
    if (!selectedPort) return;
    
    // For now, use the default vehicle or first vehicle
    const defaultVehicle = vehicles.find(v => v.is_default) || vehicles[0];
    
    if (!defaultVehicle) {
      alert("Please add a vehicle first in your profile.");
      return;
    }
    
    setReserving(true);
    try {
      const res = await api.post('/reservations', {
        port_id: selectedPort.port_id,
        vehicle_id: defaultVehicle.vehicle_id
      });
      
      if (res.data.success) {
        alert("Reservation successful!");
        setIsModalOpen(false);
        navigate('/driver'); // Navigate back to dashboard to see active reservation
      } else {
        alert(res.data.message || "Failed to reserve");
      }
    } catch (err: any) {
      alert(err.response?.data?.message || "Error reserving port");
    } finally {
      setReserving(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading...</div>;
  if (error) return <div className="p-8 text-center text-red-500">{error}</div>;
  if (!station) return <div className="p-8 text-center">Station not found</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <button 
        onClick={() => navigate('/driver/search')}
        className="flex items-center text-emerald-600 hover:text-emerald-700 transition-colors mb-4"
      >
        <ArrowLeft className="w-4 h-4 mr-1" /> Back to Search
      </button>

      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">{station.name}</h1>
        
        <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-6">
          <span className="flex items-center gap-1">
            <Zap className="w-4 h-4 text-yellow-500" /> ₹{station.price_per_kwh}/kWh
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-4 h-4" /> {station.opening_time_local || '24/7'} - {station.closing_time_local || '24/7'}
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="w-4 h-4" /> Lat: {station.lat.toFixed(4)}, Lng: {station.lng.toFixed(4)}
          </span>
        </div>
        
        <h2 className="text-xl font-semibold text-gray-800 mb-4 border-b pb-2">Available Ports</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {station.ports.map((port: any) => (
            <div 
              key={port.port_id} 
              className={`p-4 rounded-xl border ${port.status === 'Available' ? 'border-emerald-200 bg-emerald-50' : 'border-gray-200 bg-gray-50'} transition-colors`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className="font-medium text-gray-800">{port.connector_type}</span>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                  port.status === 'Available' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-200 text-gray-700'
                }`}>
                  {port.status}
                </span>
              </div>
              <div className="text-sm text-gray-500 mb-4">
                {port.charger_type}
              </div>
              
              <button
                disabled={port.status !== 'Available' || reserving}
                onClick={() => {
                  setSelectedPort(port);
                  setIsModalOpen(true);
                }}
                className="w-full px-4 py-2 bg-emerald-600 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-emerald-700 transition-colors"
              >
                Reserve Port
              </button>
            </div>
          ))}
          {station.ports.length === 0 && (
            <div className="col-span-full text-center text-gray-500 py-8">
              No charging ports found at this station.
            </div>
          )}
        </div>
      </div>

      {selectedPort && (
        <ReservationModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onConfirm={handleReserve}
          stationName={station.name}
          portId={selectedPort.port_id}
          pricePerKwh={station.price_per_kwh}
        />
      )}
    </div>
  );
};
