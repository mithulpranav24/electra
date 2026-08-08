import React, { useState, useEffect } from 'react';
import { operatorService, authService } from '../../services/api';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix for default leaflet icons in React
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

function LocationMarker({ position, setPosition }: { position: [number, number], setPosition: (p: [number, number]) => void }) {
  useMapEvents({
    click(e) {
      setPosition([e.latlng.lat, e.latlng.lng]);
    },
  });

  return position === null ? null : (
    <Marker position={position}></Marker>
  );
}

export default function OperatorDashboard() {
  const [stations, setStations] = useState<any[]>([]);
  const [companyId, setCompanyId] = useState<string>(''); 
  const { logout } = useAuth();
  
  const [newStation, setNewStation] = useState({
    name: '',
    price_per_kwh: '0.50',
    minimum_session_fee: '1.00',
    timezone: 'UTC',
    lat: 37.7749,
    lng: -122.4194
  });

  const [newPort, setNewPort] = useState({
    station_id: '',
    qr_code: '',
    connector_type: 'CCS2',
    charger_type: 'DC Fast'
  });

  const navigate = useNavigate();

  const loadStations = async (cId: string) => {
    try {
      if (cId) {
        const data = await operatorService.getStations(cId);
        setStations(data);
      }
    } catch (error) {
      console.error('Failed to load stations', error);
    }
  };

  useEffect(() => {
    const fetchCompanies = async () => {
      try {
        const comps = await authService.getMyCompanies();
        if (comps && comps.length > 0) {
          const firstCompanyId = comps[0].company_id;
          setCompanyId(firstCompanyId);
          loadStations(firstCompanyId);
        }
      } catch (err) {
        console.error("Failed to fetch companies", err);
      }
    };
    fetchCompanies();
  }, []);

  const handleCreateStation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...newStation,
        price_per_kwh: parseFloat(newStation.price_per_kwh),
        minimum_session_fee: parseFloat(newStation.minimum_session_fee)
      };
      await operatorService.createStation(companyId, payload);
      alert('Station created!');
      loadStations(companyId);
    } catch (error) {
      console.error('Failed to create station', error);
      alert('Error creating station. Make sure you belong to the company ID used.');
    }
  };

  const handleCreatePort = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPort.station_id) return alert('Select a station first');
    try {
      await operatorService.createPort(newPort.station_id, newPort);
      alert('Port created!');
      loadStations(companyId);
      setNewPort({ ...newPort, qr_code: '' });
    } catch (error) {
      console.error('Failed to create port', error);
      alert('Error creating port');
    }
  };
  
  const handleDeleteStation = async (id: string) => {
    if(!window.confirm("Delete this station?")) return;
    try {
      await operatorService.deleteStation(id);
      loadStations(companyId);
    } catch(e) { alert('Error deleting station'); }
  };
  
  const handleDeletePort = async (id: string) => {
    if(!window.confirm("Delete this port?")) return;
    try {
      await operatorService.deletePort(id);
      loadStations(companyId);
    } catch(e) { alert('Error deleting port'); }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 animate-fade-in">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-emerald-500 to-teal-600">Operator Dashboard</h1>
          <p className="text-skeuo-text-muted mt-2">Manage Stations and Charging Ports</p>
        </div>
        <div className="flex gap-4">
          <button className="skeuo-btn" onClick={() => navigate('/driver/dashboard')}>
            Back to Main
          </button>
          <button className="skeuo-btn text-red-500 font-semibold" onClick={logout}>
            Logout
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="skeuo-panel p-6 space-y-6">
          <h2 className="text-xl font-semibold">Create Station</h2>
          <form onSubmit={handleCreateStation} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">Station Name</label>
                <input required type="text" className="skeuo-input" value={newStation.name} onChange={e => setNewStation({...newStation, name: e.target.value})} />
              </div>
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">Timezone</label>
                <input required type="text" className="skeuo-input" value={newStation.timezone} onChange={e => setNewStation({...newStation, timezone: e.target.value})} />
              </div>
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">Price/kWh ($)</label>
                <input required type="number" step="0.01" className="skeuo-input" value={newStation.price_per_kwh} onChange={e => setNewStation({...newStation, price_per_kwh: e.target.value})} />
              </div>
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">Min Fee ($)</label>
                <input required type="number" step="0.01" className="skeuo-input" value={newStation.minimum_session_fee} onChange={e => setNewStation({...newStation, minimum_session_fee: e.target.value})} />
              </div>
            </div>

            <div className="pt-2">
              <label className="skeuo-label block mb-2">Location (Drop Pin or Type)</label>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="skeuo-text-field-group">
                  <input type="number" step="any" className="skeuo-input text-sm" placeholder="Lat" value={newStation.lat} onChange={e => setNewStation({...newStation, lat: parseFloat(e.target.value)})} />
                </div>
                <div className="skeuo-text-field-group">
                  <input type="number" step="any" className="skeuo-input text-sm" placeholder="Lng" value={newStation.lng} onChange={e => setNewStation({...newStation, lng: parseFloat(e.target.value)})} />
                </div>
              </div>
              
              <div className="h-48 w-full rounded-xl overflow-hidden shadow-skeuo-pressed border border-white/20 dark:border-white/5 relative z-0">
                <MapContainer center={[newStation.lat, newStation.lng]} zoom={13} style={{ height: '100%', width: '100%' }}>
                  <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                  <LocationMarker position={[newStation.lat, newStation.lng]} setPosition={(p) => setNewStation({...newStation, lat: p[0], lng: p[1]})} />
                </MapContainer>
              </div>
            </div>
            
            <button type="submit" className="skeuo-btn skeuo-btn-primary w-full">Create Station</button>
          </form>
        </div>

        <div className="skeuo-panel p-6 space-y-6 flex flex-col">
          <h2 className="text-xl font-semibold">Add Charging Port</h2>
          <form onSubmit={handleCreatePort} className="space-y-4 flex-1">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Station</label>
              <select required className="skeuo-input" value={newPort.station_id} onChange={e => setNewPort({...newPort, station_id: e.target.value})}>
                <option value="">Select Station...</option>
                {stations.map(s => <option key={s.station_id} value={s.station_id}>{s.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">QR Code</label>
                <input required type="text" className="skeuo-input" value={newPort.qr_code} onChange={e => setNewPort({...newPort, qr_code: e.target.value})} />
              </div>
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">Connector Type</label>
                <select className="skeuo-input" value={newPort.connector_type} onChange={e => setNewPort({...newPort, connector_type: e.target.value})}>
                  <option>CCS2</option>
                  <option>CCS1</option>
                  <option>CHAdeMO</option>
                  <option>Type 2</option>
                </select>
              </div>
              <div className="skeuo-text-field-group col-span-2">
                <label className="skeuo-label">Charger Type</label>
                <select className="skeuo-input" value={newPort.charger_type} onChange={e => setNewPort({...newPort, charger_type: e.target.value})}>
                  <option>DC Fast</option>
                  <option>AC Level 2</option>
                  <option>Ultra Fast DC</option>
                </select>
              </div>
            </div>
            <button type="submit" className="skeuo-btn skeuo-btn-primary w-full mt-4">Add Port</button>
          </form>
        </div>
      </div>

      <div className="skeuo-panel p-6 space-y-4">
        <h2 className="text-xl font-semibold">Stations Overview</h2>
        {stations.length === 0 ? (
          <p className="text-skeuo-text-muted">No stations assigned to your company.</p>
        ) : (
          <div className="space-y-4">
            {stations.map(station => (
              <div key={station.station_id} className="p-4 rounded-xl border border-white/20 dark:border-white/5 bg-white/10 shadow-skeuo-sm">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="font-bold text-lg">{station.name}</h3>
                    <p className="text-sm text-skeuo-text-muted">Price: ${station.price_per_kwh}/kWh | Coords: {station.lat.toFixed(4)}, {station.lng.toFixed(4)}</p>
                  </div>
                  <button onClick={() => handleDeleteStation(station.station_id)} className="text-red-500 hover:text-red-600 text-sm font-semibold">Delete</button>
                </div>
                
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-skeuo-text-muted uppercase tracking-wider">Charging Ports</h4>
                  {station.ports && station.ports.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {station.ports.map((port: any) => (
                        <div key={port.port_id} className="bg-skeuo-base dark:bg-dark-skeuo-base p-3 rounded-lg shadow-skeuo-pressed-sm flex flex-col gap-1">
                          <div className="flex justify-between">
                            <span className="font-mono text-xs">{port.qr_code}</span>
                            <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${port.status === 'Available' ? 'bg-green-500/20 text-green-600' : 'bg-orange-500/20 text-orange-600'}`}>{port.status}</span>
                          </div>
                          <div className="text-sm">{port.connector_type} • {port.charger_type}</div>
                          <div className="flex justify-end gap-2 mt-2">
                            <button onClick={() => handleDeletePort(port.port_id)} className="text-xs text-red-500 font-medium">Remove</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-skeuo-text-muted">No ports found for this station.</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
