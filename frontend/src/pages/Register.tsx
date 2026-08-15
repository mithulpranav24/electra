import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, UserRound } from 'lucide-react';
import { authService } from '../services/api';
import { getErrorMessage } from '../lib/errors';
import { AuthLayout } from '../components/AuthLayout';
import { Alert } from '../ui/Feedback';
import { Field } from '../ui/Field';
import { Button, IconButton } from '../ui/Button';

export default function Register() {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPasswords, setShowPasswords] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Use at least 8 characters for your password.');
      return;
    }
    if (password !== confirmPassword) {
      setError('The passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      await authService.register({ email: email.trim(), password, ...(fullName.trim() ? { full_name: fullName.trim() } : {}) });
      navigate('/login', { replace: true, state: { registered: true } });
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'Registration failed. Review your details and try again.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout mode="register">
      <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
        {error && <Alert tone="error" title="Couldn’t create your account">{error}</Alert>}

        <Field label="Full name" optional hint="You can also add this later from your account settings.">
          {({ id, describedBy, invalid }) => (
            <div className="relative">
              <UserRound size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" aria-hidden="true" />
              <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control pl-11" type="text" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} placeholder="Your name" autoFocus />
            </div>
          )}
        </Field>

        <Field label="Email address">
          {({ id, describedBy, invalid }) => (
            <div className="relative">
              <Mail size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" aria-hidden="true" />
              <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control pl-11" type="email" autoComplete="email" inputMode="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
            </div>
          )}
        </Field>

        <Field label="Password" hint="Use 8 or more characters; common passwords are blocked.">
          {({ id, describedBy, invalid }) => (
            <div className="relative">
              <LockKeyhole size={18} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--steel)]" aria-hidden="true" />
              <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control px-11" type={showPasswords ? 'text' : 'password'} autoComplete="new-password" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Create a password" required />
              <IconButton label={showPasswords ? 'Hide passwords' : 'Show passwords'} className="absolute right-1 top-1/2 size-9 -translate-y-1/2 border-0 bg-transparent" onClick={() => setShowPasswords((value) => !value)}>{showPasswords ? <EyeOff size={18} /> : <Eye size={18} />}</IconButton>
            </div>
          )}
        </Field>

        <Field label="Confirm password">
          {({ id, describedBy, invalid }) => (
            <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" type={showPasswords ? 'text' : 'password'} autoComplete="new-password" minLength={8} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Repeat your password" required />
          )}
        </Field>

        <Button type="submit" variant="primary" size="lg" className="mt-1 w-full" isLoading={isSubmitting} icon={<ArrowRight size={18} />}>Create account</Button>
        <p className="text-center text-sm text-[var(--steel)]">Already registered? <Link to="/login" className="font-bold text-[var(--teal-dark)] underline-offset-4 hover:underline">Sign in</Link></p>
      </form>
    </AuthLayout>
  );
}
