import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import DriverLayout from './components/DriverLayout';
import Dashboard from './pages/driver/Dashboard';
import Vehicles from './pages/driver/Vehicles';
import Profile from './pages/driver/Profile';

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
            <Route path="*" element={<Navigate to="/driver/dashboard" replace />} />
          </Route>

          {/* Placeholders for other roles */}
          <Route path="/operator/*" element={<RoleProtectedRoute allowedRole="Operator"><div className="p-10 text-center">Operator Dashboard coming in Phase 4</div></RoleProtectedRoute>} />
          <Route path="/admin/*" element={<RoleProtectedRoute allowedRole="Admin"><div className="p-10 text-center">Admin Dashboard coming in Phase 4</div></RoleProtectedRoute>} />
          
          <Route path="/" element={<RootRouter />} />
          <Route path="*" element={<RootRouter />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
