import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Car, LayoutDashboard, LogOut, User as UserIcon, Zap, Wallet } from 'lucide-react';

const DriverLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/driver/dashboard', icon: <LayoutDashboard size={20} />, label: 'Overview' },
    { to: '/driver/vehicles', icon: <Car size={20} />, label: 'My Vehicles' },
    { to: '/driver/sessions', icon: <Zap size={20} />, label: 'Charging Sessions' },
    { to: '/driver/wallet', icon: <Wallet size={20} />, label: 'Wallet & Billing' },
    { to: '/driver/profile', icon: <UserIcon size={20} />, label: 'Profile' },
  ];

  return (
    <div className="min-h-screen bg-skeuo-base text-skeuo-text flex">
      {/* Sidebar */}
      <aside className="w-64 skeuo-panel m-4 flex flex-col justify-between overflow-hidden relative border border-white/20">
        <div>
          <div className="p-6 pb-2 border-b border-white/10 flex items-center gap-3">
            <div className="bg-skeuo-accent p-2 rounded-xl shadow-skeuo-pressed">
               <Zap className="text-white" size={24} />
            </div>
            <h1 className="text-2xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-blue-500 to-teal-400">Electra</h1>
          </div>
          
          {/* Feature dense quick stats block in sidebar */}
          <div className="px-6 py-4 border-b border-white/10">
            <p className="text-xs text-skeuo-text-muted uppercase font-bold tracking-wider mb-2">My Wallet</p>
            <div className="flex items-center justify-between bg-skeuo-base shadow-skeuo-pressed-sm rounded-lg p-3 border border-white/10">
              <div className="flex items-center gap-2">
                <Wallet size={16} className="text-emerald-500" />
                <span className="font-semibold">₹ {user?.wallet_balance?.toFixed(2) || '0.00'}</span>
              </div>
              <button className="text-xs bg-skeuo-accent text-white px-2 py-1 rounded shadow-sm hover:scale-105 transition-transform">Top up</button>
            </div>
          </div>

          <nav className="p-4 flex flex-col gap-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                    isActive
                      ? 'bg-skeuo-base shadow-skeuo-pressed text-skeuo-accent font-semibold border border-white/20'
                      : 'hover:bg-white/5 text-skeuo-text-muted hover:text-skeuo-text border border-transparent'
                  }`
                }
              >
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </div>

        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-3 p-3 mb-3 bg-skeuo-base shadow-skeuo-pressed-sm rounded-xl border border-white/10">
            <div className="w-10 h-10 rounded-full bg-skeuo-dark flex items-center justify-center shadow-skeuo-pressed">
              <UserIcon size={20} className="text-skeuo-text-muted" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="font-semibold text-sm truncate">{user?.full_name}</p>
              <p className="text-xs text-skeuo-text-muted truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full skeuo-btn text-red-500 hover:text-red-600 flex items-center justify-center gap-2 py-2.5 text-sm"
          >
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-8 overflow-y-auto h-screen">
        <Outlet />
      </main>
    </div>
  );
};

export default DriverLayout;
