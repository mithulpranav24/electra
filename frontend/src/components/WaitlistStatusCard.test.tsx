import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { WaitlistStatus } from '../types';
import { WaitlistStatusCard } from './WaitlistStatusCard';
import '../test/setup';

const baseStatus: WaitlistStatus = {
  waitlist_id: 'waitlist-1',
  station_id: 'station-1',
  vehicle_id: 'vehicle-1',
  joined_at: '2026-08-15T12:00:00Z',
  joined_tariff: 12,
  joined_minimum_fee: 50,
  position: 3,
};

describe('WaitlistStatusCard', () => {
  it('shows the queue position when there is no active offer', () => {
    render(<WaitlistStatusCard status={baseStatus} onConfirm={vi.fn()} onLeave={vi.fn()} />);
    expect(screen.getByText('Position 3 in queue')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirm reservation' })).not.toBeInTheDocument();
  });

  it('shows a confirm action and countdown when a port has been offered', () => {
    const offerExpiresAt = new Date(Date.now() + 60000).toISOString();
    const offeredStatus: WaitlistStatus = { ...baseStatus, offered_port_id: 'port-1', offered_at: new Date().toISOString(), offer_expires_at: offerExpiresAt };
    render(<WaitlistStatusCard status={offeredStatus} onConfirm={vi.fn()} onLeave={vi.fn()} />);
    expect(screen.getByText('Port offered')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm reservation' })).toBeInTheDocument();
  });

  it('calls onLeave when leaving the waitlist', () => {
    const onLeave = vi.fn();
    render(<WaitlistStatusCard status={baseStatus} onConfirm={vi.fn()} onLeave={onLeave} />);
    fireEvent.click(screen.getByRole('button', { name: 'Leave waitlist' }));
    expect(onLeave).toHaveBeenCalledTimes(1);
  });
});
