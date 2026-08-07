import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Mail, Lock, CreditCard, ArrowRight, ShieldCheck } from 'lucide-react';

const Register: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    try {
      // In a real flow, the mock payment would be processed here to tokenize the card.
      const response = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, role: 'Driver' }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Redirect to login after successful registration
        navigate('/login');
      } else {
        setError(data.detail || 'Registration failed');
      }
    } catch (err) {
      setError('An error occurred during registration');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="skeuo-panel w-full max-w-xl p-8 flex flex-col gap-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-skeuo-text">Create Account</h1>
          <p className="text-skeuo-text-muted mt-2">Join Electra to charge your EV anywhere</p>
        </div>

        {error && (
          <div className="bg-red-100/50 text-red-600 p-3 rounded-xl text-sm border border-red-200 text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="grid grid-cols-1 gap-5">
            <div className="skeuo-text-field-group">
              <label className="skeuo-label">Email Address</label>
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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
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
              
              <div className="skeuo-text-field-group">
                <label className="skeuo-label">Confirm Password</label>
                <div className="relative">
                  <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 text-skeuo-text-muted" size={18} />
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="skeuo-input pl-10 w-full"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 p-5 skeuo-panel bg-white/40 dark:bg-black/20 border-dashed border-2 border-skeuo-accent/30 rounded-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 bg-skeuo-accent text-white text-[10px] font-bold px-2 py-1 rounded-bl-lg">
              MOCK PAYMENT GATEWAY
            </div>
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <CreditCard size={16} className="text-skeuo-accent" />
              Payment Method (Required for Escrow)
            </h3>
            <p className="text-xs text-skeuo-text-muted mb-4">
              To guarantee recovery of penalties and enable reservations, a valid card is required. 
              <br/>(Phase 2: This is a visual placeholder to be integrated in Phase 3).
            </p>
            <div className="skeuo-text-field-group">
              <input
                type="text"
                disabled
                className="skeuo-input opacity-70 cursor-not-allowed text-center tracking-widest font-mono"
                placeholder="XXXX XXXX XXXX 4242"
              />
            </div>
          </div>

          <button type="submit" className="skeuo-btn skeuo-btn-primary mt-4">
            <span>Complete Registration</span>
            <ArrowRight size={18} />
          </button>
        </form>

        <p className="text-center text-sm text-skeuo-text-muted mt-2">
          Already have an account?{' '}
          <Link to="/login" className="text-skeuo-accent font-semibold hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Register;
