import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail } from 'lucide-react';
import { useAuth } from '../context/auth-context';
import { authService } from '../services/api';
import { getErrorMessage } from '../lib/errors';
import { AuthLayout } from '../components/AuthLayout';
import { Alert } from '../ui/Feedback';
import { Field } from '../ui/Field';
import { Button, IconButton } from '../ui/Button';

interface LoginLocationState { registered?: boolean; }

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LoginLocationState | null;

  useEffect(() => {
    if (!isAuthenticated || !user) return;
    const home = user.role === 'Driver' ? '/driver/dashboard' : user.role === 'Operator' ? '/operator/dashboard' : '/admin/dashboard';
    navigate(home, { replace: true });
  }, [isAuthenticated, navigate, user]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const response = await authService.login(email.trim(), password);
      login(response.access_token);
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'Sign-in failed. Check your details and try again.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout mode="login">
      <form onSubmit={handleSubmit} className="flex min-w-0 flex-col gap-5" noValidate>
        {state?.registered && <Alert tone="success" title="Account created">Sign in with the email and password you just registered.</Alert>}
        {error && <Alert tone="error" title="Couldn’t sign you in">{error}</Alert>}

        <Field label="Email address">
          {({ id, describedBy, invalid }) => (
            <div className="relative">
              <Mail size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" aria-hidden="true" />
              <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control field-control-leading" type="email" autoComplete="email" inputMode="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required autoFocus />
            </div>
          )}
        </Field>

        <Field label="Password">
          {({ id, describedBy, invalid }) => (
            <div className="relative">
              <LockKeyhole size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" aria-hidden="true" />
              <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control field-control-both" type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required />
              <IconButton label={showPassword ? 'Hide password' : 'Show password'} className="absolute right-1 top-1/2 size-9 -translate-y-1/2 border-0 bg-transparent" onClick={() => setShowPassword((value) => !value)}>{showPassword ? <EyeOff size={18} /> : <Eye size={18} />}</IconButton>
            </div>
          )}
        </Field>

        <Button type="submit" variant="primary" size="lg" className="mt-1 w-full" isLoading={isSubmitting} icon={<ArrowRight size={18} />}>
          Sign in
        </Button>

        <p className="text-center text-sm text-[var(--steel)]">
          New to Electra? <Link to="/register" className="font-bold text-[var(--teal-dark)] underline-offset-4 hover:underline">Create an account</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
