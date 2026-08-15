export type StatusTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

export function statusTone(status: string): StatusTone {
  const normalized = status.toLowerCase();
  if (['available', 'active', 'completed', 'confirmed'].includes(normalized)) return 'success';
  if (['reserved', 'charging', 'pending waitlist', 'deprecating'].includes(normalized)) return 'warning';
  if (['offline', 'maintenance', 'cancelled', 'inactive', 'suspended'].includes(normalized)) return 'danger';
  return 'neutral';
}
