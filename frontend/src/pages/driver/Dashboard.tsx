import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Clock, Navigation, BatteryCharging, Zap, Wallet } from 'lucide-react';
import { authService } from '../../services/api';

const Dashboard = () => {
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    authService.getDashboardData().then(setData).catch(console.error);
  }, []);

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto">
      <header className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold mb-1">Welcome back, {user?.full_name?.split(' ')[0]}</h1>
          <p className="text-skeuo-text-muted">Here's your charging overview for today.</p>
        </div>
      </header>

      {/* Quick Stats / Functional Density block */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="skeuo-panel p-5 flex flex-col gap-2">
          <div className="flex justify-between items-center text-skeuo-text-muted mb-2">
            <span className="text-sm font-semibold">Active Session</span>
            <BatteryCharging size={18} className="text-emerald-500" />
          </div>
          <p className="text-2xl font-bold text-emerald-500">{data?.active_sessions || 'None'}</p>
          <p className="text-xs text-skeuo-text-muted">Ready to charge</p>
        </div>
        
        <div className="skeuo-panel p-5 flex flex-col gap-2">
          <div className="flex justify-between items-center text-skeuo-text-muted mb-2">
            <span className="text-sm font-semibold">Upcoming Booking</span>
            <Clock size={18} className="text-blue-500" />
          </div>
          <p className="text-xl font-bold">{data?.upcoming_bookings || 'No reservations'}</p>
          <p className="text-xs text-skeuo-text-muted">Book a slot now</p>
        </div>

        <div className="skeuo-panel p-5 flex flex-col gap-2">
          <div className="flex justify-between items-center text-skeuo-text-muted mb-2">
            <span className="text-sm font-semibold">Nearest Station</span>
            <Navigation size={18} className="text-orange-500" />
          </div>
          <p className="text-xl font-bold truncate">Downtown Hub</p>
          <p className="text-xs text-skeuo-text-muted">2.4 km away • 4 ports available</p>
        </div>

        <div className="skeuo-panel p-5 flex flex-col gap-2">
          <div className="flex justify-between items-center text-skeuo-text-muted mb-2">
            <span className="text-sm font-semibold">Energy Charged</span>
            <Zap size={18} className="text-yellow-500" />
          </div>
          <p className="text-2xl font-bold">{data?.energy_charged_kwh || '0'} <span className="text-lg">kWh</span></p>
          <p className="text-xs text-skeuo-text-muted">This month</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-4">
        {/* Recent Activity */}
        <div className="skeuo-panel p-6 col-span-2">
          <h2 className="text-xl font-bold mb-4 flex items-center justify-between">
            <span>Recent Activity</span>
            <button className="text-sm text-skeuo-accent font-semibold hover:underline">View All</button>
          </h2>
          <div className="flex flex-col gap-4">
            {data?.recent_activity ? data.recent_activity.map((act: any) => (
              <div key={act.id} className="bg-skeuo-base shadow-skeuo-pressed-sm rounded-xl p-4 border border-white/20 flex items-center justify-between">
                 <div className="flex gap-4 items-center">
                    <div className="w-10 h-10 rounded-full bg-emerald-500/20 text-emerald-600 flex items-center justify-center shadow-inner">
                      <Zap size={20} />
                    </div>
                    <div>
                      <p className="font-semibold">{act.location}</p>
                      <p className="text-xs text-skeuo-text-muted">{act.date}</p>
                    </div>
                 </div>
                 <div className="text-right">
                    <p className="font-bold">{act.amount}</p>
                    <p className="text-xs text-emerald-500 font-semibold">{act.status}</p>
                 </div>
              </div>
            )) : (
              <div className="text-center py-4 text-skeuo-text-muted">No recent activity</div>
            )}

            {/* Placeholder for empty state if needed, using hardcoded for feature-dense view */}
            <div className="bg-skeuo-base shadow-skeuo-pressed-sm rounded-xl p-4 border border-white/20 flex items-center justify-between">
               <div className="flex gap-4 items-center">
                  <div className="w-10 h-10 rounded-full bg-blue-500/20 text-blue-600 flex items-center justify-center shadow-inner">
                    <Clock size={20} />
                  </div>
                  <div>
                    <p className="font-semibold">Reservation Expired</p>
                    <p className="text-xs text-skeuo-text-muted">Aug 4, 09:00</p>
                  </div>
               </div>
               <div className="text-right">
                  <p className="font-bold text-red-500">Penalty</p>
                  <p className="text-xs text-red-500 font-semibold">+1 Point</p>
               </div>
            </div>
          </div>
        </div>

        {/* Action Panel */}
        <div className="skeuo-panel p-6 flex flex-col gap-4">
          <h2 className="text-xl font-bold mb-2">Quick Actions</h2>
          <button className="skeuo-btn skeuo-btn-primary w-full justify-start py-4">
            <Zap size={20} />
            <span>Find a Station</span>
          </button>
          <button className="skeuo-btn w-full justify-start py-4">
            <Navigation size={20} />
            <span>View Map</span>
          </button>
          <button className="skeuo-btn w-full justify-start py-4">
            <Wallet size={20} />
            <span>Add Funds</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
