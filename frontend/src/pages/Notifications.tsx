import { useCallback, useEffect, useState } from 'react';
import { Bell, BellRing, CheckCheck } from 'lucide-react';
import { notificationService } from '../services/api';
import type { Notification } from '../types';
import { getErrorMessage } from '../lib/errors';
import { formatDateTime } from '../lib/format';
import { Button } from '../ui/Button';
import { EmptyState, ErrorState, LoadingState } from '../ui/Feedback';
import { PageHeader } from '../ui/Page';
import { useToast } from '../ui/ToastContext';

export default function Notifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const { pushToast } = useToast();

  const load = useCallback(async () => {
    setError('');
    setIsLoading(true);
    try {
      setNotifications(await notificationService.list());
    } catch (loadError) {
      setError(getErrorMessage(loadError, 'Notifications could not be loaded.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const handleMarkRead = async (notification: Notification) => {
    if (notification.is_read) return;
    setNotifications((current) => current.map((item) => item.notification_id === notification.notification_id ? { ...item, is_read: true } : item));
    try {
      await notificationService.markRead(notification.notification_id);
    } catch (markError) {
      pushToast({ title: 'Couldn’t mark as read', message: getErrorMessage(markError, 'Try again.'), tone: 'error' });
      void load();
    }
  };

  const handleMarkAllRead = async () => {
    setIsMarkingAll(true);
    try {
      await notificationService.markAllRead();
      setNotifications((current) => current.map((item) => ({ ...item, is_read: true })));
    } catch (markError) {
      pushToast({ title: 'Couldn’t mark all as read', message: getErrorMessage(markError, 'Try again.'), tone: 'error' });
    } finally {
      setIsMarkingAll(false);
    }
  };

  const unreadCount = notifications.filter((item) => !item.is_read).length;

  if (isLoading) return <div className="surface"><LoadingState label="Loading notifications" /></div>;
  if (error) return <ErrorState title="Notifications unavailable" description={error} onRetry={() => void load()} />;

  return (
    <div className="flex flex-col gap-6 enter-up">
      <PageHeader
        eyebrow="Stay in the loop"
        title="Notifications"
        description="Reservation, waitlist, charging, and invoice updates for your account."
        actions={unreadCount > 0 ? <Button size="sm" icon={<CheckCheck size={16} />} onClick={() => void handleMarkAllRead()} isLoading={isMarkingAll}>Mark all read</Button> : undefined}
      />

      <section className="surface overflow-hidden">
        {notifications.length === 0 ? (
          <EmptyState title="No notifications yet" description="You'll see reservation, waitlist, charging, and invoice updates here." icon={<Bell size={22} />} />
        ) : (
          <div className="divide-y divide-[var(--line)]">
            {notifications.map((notification) => (
              <button
                key={notification.notification_id}
                type="button"
                onClick={() => void handleMarkRead(notification)}
                className={`flex w-full items-start gap-3 p-4 text-left transition sm:p-5 ${notification.is_read ? 'bg-white' : 'bg-[var(--teal-soft)]/40'} hover:bg-[var(--paper-muted)]`}
              >
                <span className={`mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full ${notification.is_read ? 'bg-[var(--paper-muted)] text-[var(--steel)]' : 'bg-[var(--teal-soft)] text-[var(--teal-dark)]'}`}>
                  {notification.is_read ? <Bell size={16} /> : <BellRing size={16} />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-sm ${notification.is_read ? 'font-semibold text-[var(--ink)]' : 'font-bold text-[var(--ink)]'}`}>{notification.title}</p>
                    {!notification.is_read && <span className="size-2 shrink-0 rounded-full bg-[var(--teal)]" aria-label="Unread" />}
                  </div>
                  <p className="mt-0.5 text-sm text-[var(--steel-dark)]">{notification.message}</p>
                  <p className="mt-1.5 text-xs text-[var(--steel)]">{formatDateTime(notification.created_at)}</p>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
