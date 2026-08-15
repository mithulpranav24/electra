import { describe, expect, it } from 'vitest';
import { normalizeConnector, shortId, vehicleId } from './format';
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
});
