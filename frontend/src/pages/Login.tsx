import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { Lock, Mail, ArrowRight } from 'lucide-react';
import { api } from '../services/api';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await api.post('/auth/login', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });
      
      login(response.data.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setError(detail || 'Login failed');
      }
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="skeuo-panel w-full max-w-md p-8 flex flex-col gap-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-skeuo-text">Welcome Back</h1>
          <p className="text-skeuo-text-muted mt-2">Sign in to your Electra account</p>
        </div>

        {error && (
          <div className="bg-red-100/50 text-red-600 p-3 rounded-xl text-sm border border-red-200 text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="skeuo-text-field-group">
            <label className="skeuo-label">Email</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-skeuo-text-muted" size={18} />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="skeuo-input pl-10 w-full"
                placeholder="driver@example.com"
              />
            </div>
          </div>

          <div className="skeuo-text-field-group">
            <label className="skeuo-label">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-skeuo-text-muted" size={18} />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="skeuo-input pl-10 w-full"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button type="submit" className="skeuo-btn skeuo-btn-primary mt-2">
            <span>Sign In</span>
            <ArrowRight size={18} />
          </button>
        </form>

        <p className="text-center text-sm text-skeuo-text-muted mt-4">
          Don't have an account?{' '}
          <Link to="/register" className="text-skeuo-accent font-semibold hover:underline">
            Register here
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
