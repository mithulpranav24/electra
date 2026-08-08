import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import DriverLayout from './components/DriverLayout';
import Dashboard from './pages/driver/Dashboard';
import Vehicles from './pages/driver/Vehicles';
import Profile from './pages/driver/Profile';
import Wallet from './pages/driver/Wallet';

import AdminDashboard from './pages/admin/Dashboard';
import OperatorDashboard from './pages/operator/Dashboard';

// Global loading screen during auth init
const GlobalLoader = () => (
  <div className="min-h-screen flex items-center justify-center bg-skeuo-base">
    <div className="animate-pulse flex flex-col items-center gap-4">
      <div className="w-16 h-16 rounded-full border-4 border-skeuo-accent border-t-transparent animate-spin shadow-skeuo-pressed"></div>
      <p className="text-skeuo-text-muted font-bold tracking-widest uppercase">Initializing</p>
    </div>
  </div>
);

const RoleProtectedRoute = ({ children, allowedRole }: { children: React.ReactNode, allowedRole: string }) => {
  const { isAuthenticated, isLoading, user } = useAuth();
  
  if (isLoading) {
    return <GlobalLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user?.role !== allowedRole) {
    // Redirect to the correct dashboard if accessing a disallowed route
    if (user?.role === 'Driver') return <Navigate to="/driver/dashboard" replace />;
    if (user?.role === 'Operator') return <Navigate to="/operator/dashboard" replace />;
    if (user?.role === 'Admin') return <Navigate to="/admin/dashboard" replace />;
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

// Route wrapper to handle initial root path logic
const RootRouter = () => {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <GlobalLoader />;
  }

  if (isAuthenticated && user) {
    if (user.role === 'Driver') return <Navigate to="/driver/dashboard" replace />;
    if (user.role === 'Operator') return <Navigate to="/operator/dashboard" replace />;
    if (user.role === 'Admin') return <Navigate to="/admin/dashboard" replace />;
  }

  return <Navigate to="/login" replace />;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Driver Routes */}
          <Route path="/driver" element={<RoleProtectedRoute allowedRole="Driver"><DriverLayout /></RoleProtectedRoute>}>
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="vehicles" element={<Vehicles />} />
            <Route path="profile" element={<Profile />} />
            <Route path="wallet" element={<Wallet />} />
            <Route path="*" element={<Navigate to="/driver/dashboard" replace />} />
          </Route>

          {/* Operator and Admin Routes */}
          <Route path="/operator/dashboard" element={<RoleProtectedRoute allowedRole="Operator"><OperatorDashboard /></RoleProtectedRoute>} />
          <Route path="/admin/dashboard" element={<RoleProtectedRoute allowedRole="Admin"><AdminDashboard /></RoleProtectedRoute>} />
          
          <Route path="/" element={<RootRouter />} />
          <Route path="*" element={<RootRouter />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
