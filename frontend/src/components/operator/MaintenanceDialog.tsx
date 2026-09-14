import { useEffect, useState } from 'react';
import type { ChargingPort, MaintenanceSchedule } from '../../types';
import { maintenanceService } from '../../services/api';
import { getErrorMessage } from '../../lib/errors';
import { Alert } from '../../ui/Feedback';
import { Field } from '../../ui/Field';
import { Button } from '../../ui/Button';
import { Dialog } from '../../ui/Dialog';

interface MaintenanceDialogProps {
  open: boolean;
  port: ChargingPort | null;
  onClose: () => void;
  onSuccess: (schedule: MaintenanceSchedule) => void;
}

function toLocalInputValue(date: Date) {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function MaintenanceDialog({ open, port, onClose, onSuccess }: MaintenanceDialogProps) {
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError('');
    const now = new Date();
    setStartTime(toLocalInputValue(now));
    setEndTime(toLocalInputValue(new Date(now.getTime() + 2 * 60 * 60 * 1000)));
  }, [open]);

  const isImmediate = startTime && new Date(startTime).getTime() <= Date.now() + 60_000;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!port) return;
    setError('');
    setIsSubmitting(true);
    try {
      const schedule = await maintenanceService.schedule({
        port_id: port.port_id,
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
      });
      onSuccess(schedule);
    } catch (submitError) {
      setError(getErrorMessage(submitError, 'The maintenance window could not be scheduled.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Schedule maintenance"
      description={port ? `Port ${port.qr_code} · ${port.connector_type}` : undefined}
      size="sm"
      preventClose={isSubmitting}
      footer={<><Button onClick={onClose} disabled={isSubmitting}>Cancel</Button><Button type="submit" form="maintenance-form" variant="primary" isLoading={isSubmitting}>Schedule</Button></>}
    >
      <form id="maintenance-form" onSubmit={handleSubmit} className="flex flex-col gap-5">
        {error && <Alert tone="error" title="Couldn’t schedule maintenance">{error}</Alert>}
        <Field label="Starts">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} type="datetime-local" className="field-control" value={startTime} onChange={(event) => setStartTime(event.target.value)} required />}</Field>
        <Field label="Ends">{({ id, describedBy, invalid }) => <input id={id} aria-describedby={describedBy} aria-invalid={invalid} type="datetime-local" className="field-control" value={endTime} min={startTime} onChange={(event) => setEndTime(event.target.value)} required />}</Field>
        {isImmediate ? (
          <Alert tone="warning" title="This takes effect immediately">
            A pending reservation or waitlist offer on this port will be cancelled without penalty. An active session will be ended now, billed only for energy delivered.
          </Alert>
        ) : (
          <Alert tone="info" title="Scheduled for later">
            If the port is Charging when this window begins, the current session finishes normally and the port then moves to Maintenance.
          </Alert>
        )}
      </form>
    </Dialog>
  );
}
