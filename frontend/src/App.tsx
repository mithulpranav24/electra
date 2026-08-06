import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';

const DashboardPlaceholder = () => {
  const { logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="skeuo-panel p-10 flex flex-col items-center gap-6 text-center max-w-lg">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-skeuo-text-muted">You have successfully logged in. The full dashboard with CRUD operations for Vehicles will be built in the next step.</p>
        <button onClick={logout} className="skeuo-btn text-red-500 hover:text-red-600 font-semibold mt-4">
          Logout
        </button>
      </div>
    </div>
  );
};

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <DashboardPlaceholder />
              </ProtectedRoute>
            } 
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
