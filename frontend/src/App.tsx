import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Zap } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import type { UserRole } from './types';
import { ToastProvider } from './ui/ToastProvider';
import { AppShell } from './components/AppShell';
import Login from './pages/Login';
import Register from './pages/Register';
import DriverDashboard from './pages/driver/Dashboard';
import Vehicles from './pages/driver/Vehicles';
import Profile from './pages/driver/Profile';
import Wallet from './pages/driver/Wallet';
import { SearchStations } from './pages/driver/SearchStations';
import { StationDetails } from './pages/driver/StationDetails';
import Sessions from './pages/driver/Sessions';
import AdminDashboard from './pages/admin/Dashboard';
import OperatorDashboard from './pages/operator/Dashboard';

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
              <Route path="profile" element={<Profile />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Route>

            <Route path="/operator" element={<RoleProtectedRoute allowedRole="Operator"><AppShell /></RoleProtectedRoute>}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<OperatorDashboard />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Route>

            <Route path="/admin" element={<RoleProtectedRoute allowedRole="Admin"><AppShell /></RoleProtectedRoute>}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<AdminDashboard />} />
              <Route path="*" element={<Navigate to="dashboard" replace />} />
            </Route>

            <Route path="/" element={<RootRouter />} />
            <Route path="*" element={<RootRouter />} />
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  );
}
