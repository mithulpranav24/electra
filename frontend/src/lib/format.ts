export const formatCurrency = (value: number | string, maximumFractionDigits = 2) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits }).format(Number(value) || 0);

// The backend (per Architecture.md, "All times are UTC") sends naive ISO
// timestamps with no "Z" or offset, e.g. "2026-09-09T11:05:49.564160". Per
// the JS Date spec, a date-time string with no timezone designator is parsed
// as *local* time, not UTC - so in any non-UTC browser, plain `new Date(value)`
// silently reads the wrong instant (and arithmetic against Date.now() breaks
// outright). Treat every backend timestamp as UTC unless it already carries
// its own zone.
export const parseUtc = (value: string) => new Date(/[Zz]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);

export const formatDateTime = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(parseUtc(value));

export const formatDate = (value: string) =>
  new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(parseUtc(value));

export const shortId = (value: string, length = 8) => value.length > length ? `${value.slice(0, length)}…` : value;
export const vehicleId = (vehicle: { vehicle_id?: string; id?: string }) => vehicle.vehicle_id || vehicle.id || '';
export const normalizeConnector = (value: string) => value.replace(/\s+/g, '').toLowerCase();
