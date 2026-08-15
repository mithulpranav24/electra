import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Building2,
  Car,
  CircleUserRound,
  LayoutDashboard,
  LogOut,
  MapPinned,
  Search,
  Wallet,
  Zap,
  type LucideIcon,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import type { UserRole } from '../types';
import { formatCurrency } from '../lib/format';
import { BrandMark } from './BrandMark';
import { Button } from '../ui/Button';

interface NavigationItem {
  to: string;
  label: string;
  shortLabel?: string;
  icon: LucideIcon;
  mobile?: boolean;
}

const navigation: Record<UserRole, NavigationItem[]> = {
  Driver: [
    { to: '/driver/dashboard', label: 'Home', icon: LayoutDashboard, mobile: true },
    { to: '/driver/search', label: 'Find charging', shortLabel: 'Find', icon: Search, mobile: true },
    { to: '/driver/sessions', label: 'Activity', icon: Zap, mobile: true },
    { to: '/driver/vehicles', label: 'Vehicles', icon: Car, mobile: true },
    { to: '/driver/wallet', label: 'Wallet & billing', shortLabel: 'Wallet', icon: Wallet, mobile: true },
    { to: '/driver/profile', label: 'Account', icon: CircleUserRound },
  ],
  Operator: [{ to: '/operator/dashboard', label: 'Station operations', shortLabel: 'Operations', icon: MapPinned, mobile: true }],
  Admin: [{ to: '/admin/dashboard', label: 'Organization control', shortLabel: 'Organizations', icon: Building2, mobile: true }],
};

function isItemActive(pathname: string, item: NavigationItem) {
  if (pathname === item.to) return true;
  return item.to === '/driver/search' && pathname.startsWith('/driver/station/');
}

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const role = user?.role ?? 'Driver';
  const items = navigation[role];
  const firstName = user?.full_name?.trim().split(/\s+/)[0] || 'there';

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[17rem_minmax(0,1fr)]">
      <aside className="app-scrollbar sticky top-0 hidden h-screen flex-col overflow-y-auto bg-[var(--night)] text-white lg:flex">
        <div className="border-b border-white/10 px-6 py-6"><BrandMark inverse /></div>
        <div className="px-6 py-5">
          <p className="text-[0.68rem] font-extrabold uppercase tracking-[0.17em] text-white/45">{role} workspace</p>
          <p className="mt-1 truncate font-display text-lg font-bold">Hello, {firstName}</p>
        </div>

        <nav className="relative flex-1 px-3" aria-label="Primary navigation">
          <div className="absolute bottom-4 left-[2.05rem] top-4 w-px bg-white/10" aria-hidden="true" />
          <div className="relative flex flex-col gap-1">
            {items.map((item) => {
              const Icon = item.icon;
              const active = isItemActive(location.pathname, item);
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={`group flex min-h-12 items-center gap-3 rounded-[0.7rem] px-3.5 text-sm font-bold transition ${active ? 'bg-white text-[var(--night)] shadow-sm' : 'text-white/65 hover:bg-white/8 hover:text-white'}`}
                  aria-current={active ? 'page' : undefined}
                >
                  <span className={`relative z-10 flex size-7 items-center justify-center rounded-full ${active ? 'bg-[var(--amber)] text-[var(--night)]' : 'bg-[var(--night-raised)] text-white/70 group-hover:text-white'}`}>
                    <Icon size={16} strokeWidth={2.25} />
                  </span>
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>

        <div className="m-3 mt-6 rounded-[var(--radius-md)] border border-white/10 bg-white/5 p-3">
          {role === 'Driver' && (
            <NavLink to="/driver/wallet" className="mb-3 block rounded-lg border border-white/10 bg-black/10 p-3 hover:border-white/20">
              <p className="text-[0.68rem] font-bold uppercase tracking-[0.13em] text-white/45">Available balance</p>
              <p className="font-data mt-1 text-lg font-bold text-[var(--amber)]">{formatCurrency(user?.wallet_balance ?? 0)}</p>
            </NavLink>
          )}
          <div className="mb-3 flex items-center gap-3 px-1">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/10 text-white/70"><CircleUserRound size={19} /></div>
            <div className="min-w-0">
              <p className="truncate text-sm font-bold">{user?.full_name || 'Electra user'}</p>
              <p className="truncate text-xs text-white/45">{user?.email}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" className="w-full !text-white/70 hover:!bg-white/8 hover:!text-white" icon={<LogOut size={16} />} onClick={handleLogout}>Sign out</Button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-[var(--line)] bg-[var(--porcelain)]/95 px-4 backdrop-blur lg:hidden">
          <BrandMark />
          <div className="flex items-center gap-2">
            {role === 'Driver' && <NavLink to="/driver/wallet" className="font-data rounded-full bg-[var(--amber-soft)] px-3 py-1.5 text-xs font-bold text-[#65470a]">{formatCurrency(user?.wallet_balance ?? 0, 0)}</NavLink>}
            {role === 'Driver' ? (
              <NavLink to="/driver/profile" className="flex size-10 items-center justify-center rounded-full border border-[var(--line)] bg-white" aria-label="Open account"><CircleUserRound size={20} /></NavLink>
            ) : (
              <button type="button" className="flex size-10 items-center justify-center rounded-full border border-[var(--line)] bg-white" onClick={handleLogout} aria-label="Sign out"><LogOut size={19} /></button>
            )}
          </div>
        </header>

        <main className="mx-auto min-h-screen w-full max-w-[var(--content-max)] px-4 pb-28 pt-6 sm:px-6 sm:pt-8 lg:px-8 lg:pb-12 xl:px-10">
          <Outlet />
        </main>

        <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-[var(--line)] bg-white/96 px-1 pb-[max(0.35rem,env(safe-area-inset-bottom))] pt-1.5 backdrop-blur lg:hidden" aria-label="Mobile navigation">
          <div className="mx-auto flex max-w-xl items-stretch justify-around">
            {items.filter((item) => item.mobile).map((item) => {
              const Icon = item.icon;
              const active = isItemActive(location.pathname, item);
              return (
                <NavLink key={item.to} to={item.to} className={`flex min-h-14 min-w-14 flex-1 flex-col items-center justify-center gap-0.5 rounded-lg px-1 text-[0.66rem] font-bold transition ${active ? 'text-[var(--teal-dark)]' : 'text-[var(--steel)]'}`} aria-current={active ? 'page' : undefined}>
                  <Icon size={20} strokeWidth={active ? 2.5 : 2} />
                  <span className="max-w-full truncate">{item.shortLabel ?? item.label}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>
      </div>
    </div>
  );
}
