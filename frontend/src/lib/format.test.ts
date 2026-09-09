import { describe, expect, it } from 'vitest';
import { normalizeConnector, parseUtc, shortId, vehicleId } from './format';
import { statusTone } from './status';

describe('frontend contract helpers', () => {
  it('matches spaced and compact connector names', () => {
    expect(normalizeConnector('Type 2')).toBe(normalizeConnector('Type2'));
    expect(normalizeConnector(' CCS2 ')).toBe('ccs2');
  });

  it('preserves the vehicle_id contract with the legacy id fallback', () => {
    expect(vehicleId({ vehicle_id: 'primary', id: 'legacy' })).toBe('primary');
    expect(vehicleId({ id: 'legacy' })).toBe('legacy');
  });

  it('formats long identifiers and known statuses consistently', () => {
    expect(shortId('1234567890', 6)).toBe('123456…');
    expect(statusTone('Available')).toBe('success');
    expect(statusTone('Pending Waitlist')).toBe('warning');
    expect(statusTone('Offline')).toBe('danger');
  });

  it('treats naive backend timestamps (no zone suffix) as UTC', () => {
    // The backend ("All times are UTC" per Architecture.md) sends naive ISO
    // strings with no Z/offset. A plain `new Date(...)` on that string is
    // parsed as local time by the JS spec, silently misreading the instant
    // in any non-UTC browser - parseUtc must not fall into that trap.
    expect(parseUtc('2026-09-09T11:05:49.564160').getTime()).toBe(new Date('2026-09-09T11:05:49.564Z').getTime());
    // Already-zoned strings must be passed through untouched.
    expect(parseUtc('2026-09-09T11:05:49Z').getTime()).toBe(new Date('2026-09-09T11:05:49Z').getTime());
    expect(parseUtc('2026-09-09T11:05:49+05:30').getTime()).toBe(new Date('2026-09-09T11:05:49+05:30').getTime());
  });
});
