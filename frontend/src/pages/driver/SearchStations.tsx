import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { api, searchService, favoriteService } from '../../services/api';
import { Search, MapPin, Zap, Filter, History, Heart } from 'lucide-react';

// Fix Leaflet default icon issue in React
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface Station {
  station_id: string;
  name: string;
  price_per_kwh: number;
  lat: number;
  lng: number;
  ports: any[];
}

export const SearchStations: React.FC = () => {
  const [stations, setStations] = useState<Station[]>([]);
  const [recentStations, setRecentStations] = useState<Station[]>([]);
  const [favorites, setFavorites] = useState<any[]>([]);
  const [radius, setRadius] = useState(10);
  const [connectorType, setConnectorType] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  // Mock user location (e.g., center of city)
  const userLat = 12.9716;
  const userLng = 77.5946;

  const handleSearch = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.post('/search/stations', {
        lat: userLat,
        lng: userLng,
        radius_km: radius,
        connector_type: connectorType || null,
      });
      if (response.data.success) {
        setStations(response.data.data);
      } else {
        setError(response.data.message || 'Failed to fetch stations');
      }
    } catch (err: any) {
      setError(err.response?.data?.message || 'An error occurred during search');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleSearch();
    
    // Fetch recents and favorites
    searchService.getRecentStations().then(setRecentStations).catch(console.error);
    favoriteService.getFavorites().then(setFavorites).catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">Find a Charger</h1>
        <p className="text-gray-500 mt-1">Search for nearby charging stations.</p>
      </div>

      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-wrap gap-4 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 mb-1">Search Radius (km)</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="number"
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all"
            />
          </div>
        </div>

        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-gray-700 mb-1">Connector Type</label>
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <select
              value={connectorType}
              onChange={(e) => setConnectorType(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all appearance-none"
            >
              <option value="">Any</option>
              <option value="CCS2">CCS2</option>
              <option value="CHAdeMO">CHAdeMO</option>
              <option value="Type 2">Type 2</option>
            </select>
          </div>
        </div>

        <button
          onClick={handleSearch}
          disabled={loading}
          className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-all shadow-md font-medium disabled:opacity-70 h-[42px]"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-lg text-red-700">
          <p>{error}</p>
        </div>
      )}

      <div className="h-[600px] bg-gray-100 rounded-xl overflow-hidden shadow-inner border border-gray-200">
        <MapContainer center={[userLat, userLng]} zoom={12} className="w-full h-full z-0">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          <Marker position={[userLat, userLng]}>
            <Popup>
              <strong>You are here</strong>
            </Popup>
          </Marker>

          {stations.map((station) => (
            <Marker key={station.station_id} position={[station.lat, station.lng]}>
              <Popup>
                <div className="p-1">
                  <h3 className="font-bold text-gray-800 mb-1">{station.name}</h3>
                  <div className="text-sm text-gray-600 mb-2 flex flex-col gap-1">
                    <span className="flex items-center gap-1"><Zap className="w-3 h-3 text-yellow-500"/> ₹{station.price_per_kwh}/kWh</span>
                    <span className="flex items-center gap-1"><MapPin className="w-3 h-3"/> {station.ports.length} Ports Available</span>
                  </div>
                  <button
                    onClick={() => navigate(`/driver/station/${station.station_id}`)}
                    className="w-full mt-2 bg-emerald-600 text-white py-1.5 rounded-lg text-sm hover:bg-emerald-700 transition-colors"
                  >
                    View Details
                  </button>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4">
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
            <History className="w-5 h-5 text-gray-500" /> Recent Stations
          </h2>
          {recentStations.length > 0 ? (
            <ul className="space-y-3">
              {recentStations.map(station => (
                <li key={station.station_id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition cursor-pointer" onClick={() => navigate(`/driver/station/${station.station_id}`)}>
                  <div>
                    <h3 className="font-semibold text-gray-800">{station.name}</h3>
                    <span className="text-xs text-gray-500 flex items-center gap-1"><Zap className="w-3 h-3 text-yellow-500" /> ₹{station.price_per_kwh}/kWh</span>
                  </div>
                  <span className="text-sm font-medium text-emerald-600">View</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No recently viewed stations.</p>
          )}
        </div>

        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
          <h2 className="text-xl font-bold text-gray-800 mb-4 flex items-center gap-2">
            <Heart className="w-5 h-5 text-red-500" /> Favorites
          </h2>
          {favorites.length > 0 ? (
            <ul className="space-y-3">
              {favorites.map(fav => (
                <li key={fav.station_id} className="flex justify-between items-center p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition cursor-pointer" onClick={() => navigate(`/driver/station/${fav.station_id}`)}>
                  <div>
                    <h3 className="font-semibold text-gray-800">{fav.station.name}</h3>
                    <span className="text-xs text-gray-500 flex items-center gap-1"><Zap className="w-3 h-3 text-yellow-500" /> ₹{fav.station.price_per_kwh}/kWh</span>
                  </div>
                  <span className="text-sm font-medium text-emerald-600">View</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">You haven't saved any stations yet.</p>
          )}
        </div>
      </div>
    </div>
  );
};
