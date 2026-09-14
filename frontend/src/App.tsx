import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Zap } from 'lucide-react';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/auth-context';
import type { UserRole } from './types';
import { ToastProvider } from './ui/ToastProvider';
import { AppShell } from './components/AppShell';

const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const DriverDashboard = lazy(() => import('./pages/driver/Dashboard'));
const Vehicles = lazy(() => import('./pages/driver/Vehicles'));
const Profile = lazy(() => import('./pages/driver/Profile'));
const Wallet = lazy(() => import('./pages/driver/Wallet'));
const SearchStations = lazy(async () => ({ default: (await import('./pages/driver/SearchStations')).SearchStations }));
const StationDetails = lazy(async () => ({ default: (await import('./pages/driver/StationDetails')).StationDetails }));
const Sessions = lazy(() => import('./pages/driver/Sessions'));
const AdminDashboard = lazy(() => import('./pages/admin/Dashboard'));
const AdminReports = lazy(() => import('./pages/admin/Reports'));
const OperatorDashboard = lazy(() => import('./pages/operator/Dashboard'));
const OperatorReports = lazy(() => import('./pages/operator/Reports'));
const Notifications = lazy(() => import('./pages/Notifications'));

function GlobalLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--night)] text-white" role="status">
      <div className="flex flex-col items-center gap-4">
        <div className="relative flex size-14 items-center justify-center rounded-2xl bg-[var(--amber)] text-[var(--night)]">
          <Zap size={28} strokeWidth={2.6} />
          <span className="absolute inset-[-0.45rem] animate-ping rounded-[1.25rem] border border-[var(--amber)]/30" aria-hidden="true" />
        </div>
        <p className="text-sm font-bold tracking-wide text-white/65">Preparing your workspace</p>
      </div>
    </div>
  );
}

function roleHome(role?: UserRole) {
  if (role === 'Driver') return '/driver/dashboard';
  if (role === 'Operator') return '/operator/dashboard';
  if (role === 'Admin') return '/admin/dashboard';
  return '/login';
}

function RoleProtectedRoute({ children, allowedRole }: { children: ReactNode; allowedRole: UserRole }) {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return <GlobalLoader />;
  if (!isAuthenticated || !user) return <Navigate to="/login" replace />;
  if (user.role !== allowedRole) return <Navigate to={roleHome(user.role)} replace />;
  return children;
}

function RootRouter() {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return <GlobalLoader />;
  return <Navigate to={isAuthenticated ? roleHome(user?.role) : '/login'} replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Suspense fallback={<GlobalLoader />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route path="/driver" element={<RoleProtectedRoute allowedRole="Driver"><AppShell /></RoleProtectedRoute>}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<DriverDashboard />} />
              <Route path="search" element={<SearchStations />} />
              <Route path="station/:id" element={<StationDetails />} />
              <Route path="sessions" element={<Sessions />} />
              <Route path="vehicles" element={<Vehicles />} />
              <Route path="wallet" element={<Wallet />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="profile" element={<Profile />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Route>

            <Route path="/operator" element={<RoleProtectedRoute allowedRole="Operator"><AppShell /></RoleProtectedRoute>}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<OperatorDashboard />} />
              <Route path="reports" element={<OperatorReports />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Route>

            <Route path="/admin" element={<RoleProtectedRoute allowedRole="Admin"><AppShell /></RoleProtectedRoute>}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="reports" element={<AdminReports />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Route>

            <Route path="/" element={<RootRouter />} />
            <Route path="*" element={<RootRouter />} />
          </Routes>
          </Suspense>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
