export const formatCurrency = (value: number | string, maximumFractionDigits = 2) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits }).format(Number(value) || 0);

export const formatDateTime = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export const formatDate = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(new Date(value));

export const shortId = (value: string, length = 8) => value.length > length ? `${value.slice(0, length)}…` : value;
export const vehicleId = (vehicle: { vehicle_id?: string; id?: string }) => vehicle.vehicle_id || vehicle.id || '';
export const normalizeConnector = (value: string) => value.replace(/\s+/g, '').toLowerCase();
