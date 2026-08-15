import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarDays, KeyRound, Save, ShieldAlert, UserRound } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { authService } from '../../services/api';
import { formatDate } from '../../lib/format';
import { getErrorMessage } from '../../lib/errors';
import { Button } from '../../ui/Button';
import { ConfirmDialog } from '../../ui/ConfirmDialog';
import { Alert } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { PageHeader, SectionHeader } from '../../ui/Page';
import { useToast } from '../../ui/ToastContext';
import { Badge } from '../../ui/Badge';

export default function Profile() {
  const { user, fetchUser, logout } = useAuth();
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const [profile, setProfile] = useState({ full_name: '', phone_number: '' });
  const [password, setPassword] = useState({ current: '', next: '', confirm: '' });
  const [profileError, setProfileError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingPassword, setIsSavingPassword] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    if (user) setProfile({ full_name: user.full_name ?? '', phone_number: user.phone_number ?? '' });
  }, [user]);

  const handleProfileSave = async (event: React.FormEvent) => {
    event.preventDefault();
    setProfileError('');
    setIsSavingProfile(true);
    try {
      await authService.updateProfile({ full_name: profile.full_name.trim(), phone_number: profile.phone_number.trim() });
      await fetchUser();
      pushToast({ title: 'Profile updated', message: 'Your account details are up to date.', tone: 'success' });
    } catch (saveError) {
      setProfileError(getErrorMessage(saveError, 'Your profile could not be updated.'));
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handlePasswordSave = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordError('');
    if (password.next.length < 8) {
      setPasswordError('The new password must contain at least 8 characters.');
      return;
    }
    if (password.next !== password.confirm) {
      setPasswordError('The new passwords do not match.');
      return;
    }
    setIsSavingPassword(true);
    try {
      await authService.updatePassword(password.current, password.next);
      setPassword({ current: '', next: '', confirm: '' });
      pushToast({ title: 'Password changed', message: 'Use your new password the next time you sign in.', tone: 'success' });
    } catch (saveError) {
      setPasswordError(getErrorMessage(saveError, 'Your password could not be changed.'));
    } finally {
      setIsSavingPassword(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await authService.deleteAccount();
      await logout();
      navigate('/login', { replace: true });
    } catch (deleteError) {
      setDeleteOpen(false);
      pushToast({ title: 'Couldn’t close the account', message: getErrorMessage(deleteError, 'Resolve active reservations or charging sessions and try again.'), tone: 'error' });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex flex-col gap-7 enter-up">
      <PageHeader eyebrow="Account" title="Profile & security" description="Manage the details tied to your driver account." />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <form onSubmit={handleProfileSave} className="surface p-5 sm:p-6">
          <SectionHeader title="Personal details" description="Your email remains the identifier used to sign in." />
          {profileError && <Alert tone="error" className="mt-5">{profileError}</Alert>}
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <Field label="Full name">
              {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={profile.full_name} onChange={(event) => setProfile((current) => ({ ...current, full_name: event.target.value }))} autoComplete="name" required />}
            </Field>
            <Field label="Phone number" optional>
              {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" value={profile.phone_number} onChange={(event) => setProfile((current) => ({ ...current, phone_number: event.target.value }))} autoComplete="tel" inputMode="tel" placeholder="+91 98765 43210" />}
            </Field>
          </div>
          <Field label="Email address" hint="Email changes are not supported by the current account API." className="mt-5">
            {({ id, describedBy }) => <input id={id} aria-describedby={describedBy} className="field-control" value={user?.email ?? ''} type="email" disabled />}
          </Field>
          <div className="mt-6 flex justify-end border-t border-[var(--line)] pt-5"><Button type="submit" variant="primary" icon={<Save size={17} />} isLoading={isSavingProfile}>Save details</Button></div>
        </form>

        <aside className="surface p-5 sm:p-6">
          <div className="flex size-14 items-center justify-center rounded-full bg-[var(--teal-soft)] text-[var(--teal-dark)]"><UserRound size={26} /></div>
          <h2 className="font-display mt-4 text-xl font-bold">{user?.full_name || 'Electra driver'}</h2>
          <p className="mt-1 break-all text-sm text-[var(--steel)]">{user?.email}</p>
          <div className="mt-5 flex flex-wrap gap-2"><Badge tone="info">{user?.role}</Badge>{user?.is_suspended && <Badge tone="danger">Suspended</Badge>}</div>
          <dl className="mt-6 border-t border-[var(--line)] pt-5">
            <div className="flex items-center justify-between gap-3"><dt className="flex items-center gap-2 text-sm text-[var(--steel)]"><CalendarDays size={17} /> Member since</dt><dd className="text-sm font-bold">{user?.created_at ? formatDate(user.created_at) : '—'}</dd></div>
          </dl>
        </aside>
      </section>

      <form onSubmit={handlePasswordSave} className="surface p-5 sm:p-6">
        <SectionHeader title="Change password" description="Use at least 8 characters; common passwords are blocked." />
        {passwordError && <Alert tone="error" className="mt-5">{passwordError}</Alert>}
        <div className="mt-5 grid gap-5 lg:grid-cols-3">
          <Field label="Current password">
            {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" type="password" autoComplete="current-password" value={password.current} onChange={(event) => setPassword((current) => ({ ...current, current: event.target.value }))} required />}
          </Field>
          <Field label="New password">
            {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" type="password" autoComplete="new-password" minLength={8} value={password.next} onChange={(event) => setPassword((current) => ({ ...current, next: event.target.value }))} required />}
          </Field>
          <Field label="Confirm new password">
            {({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} className="field-control" type="password" autoComplete="new-password" minLength={8} value={password.confirm} onChange={(event) => setPassword((current) => ({ ...current, confirm: event.target.value }))} required />}
          </Field>
        </div>
        <div className="mt-6 flex justify-end border-t border-[var(--line)] pt-5"><Button type="submit" icon={<KeyRound size={17} />} isLoading={isSavingPassword}>Change password</Button></div>
      </form>

      <section className="rounded-[var(--radius-lg)] border border-[var(--red)]/30 bg-[var(--red-soft)] p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex gap-3"><ShieldAlert size={23} className="mt-0.5 shrink-0 text-[var(--red)]" /><div><h2 className="font-display text-lg font-bold text-[var(--red-dark)]">Close account</h2><p className="mt-1 max-w-2xl text-sm text-[#74403d]">This soft-deletes the account and signs you out. Active reservations or charging sessions must be resolved first.</p></div></div>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>Close account</Button>
        </div>
      </section>

      <ConfirmDialog open={deleteOpen} onClose={() => setDeleteOpen(false)} onConfirm={() => void handleDelete()} title="Close your Electra account?" description="You will be signed out and this account will no longer be active. This action cannot be reversed from the app." confirmLabel="Close my account" isLoading={isDeleting} />
    </div>
  );
}
