import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { ChargingSessionStatus } from '../types';
import { ActiveSessionCard } from './ActiveSessionCard';
import '../test/setup';

const baseStatus: ChargingSessionStatus = {
  session_id: 'session-1',
  reservation_id: 'reservation-1',
  port_id: 'port-1',
  vehicle_id: 'vehicle-1',
  initial_battery_percentage: 20,
  target_battery_percentage: 80,
  applied_tariff: 15.5,
  start_time: '2026-08-15T12:00:00Z',
  current_battery_percentage: 50,
  target_reached: false,
  energy_delivered_kwh: 12,
  energy_cost: 186,
  idle_minutes: 0,
  idle_fee: 0,
  total_cost: 186,
  elapsed_minutes: 20,
  eta_minutes_remaining: 15,
};

describe('ActiveSessionCard', () => {
  it('shows charging status and progress while below target', () => {
    render(<ActiveSessionCard status={baseStatus} onStop={vi.fn()} />);
    expect(screen.getByText('Charging')).toBeInTheDocument();
    expect(screen.getByText('50.0%')).toBeInTheDocument();
  });

  it('flags idle time and fees once the target is reached', () => {
    const idleStatus: ChargingSessionStatus = { ...baseStatus, current_battery_percentage: 80, target_reached: true, idle_minutes: 12, idle_fee: 120, total_cost: 800 };
    render(<ActiveSessionCard status={idleStatus} onStop={vi.fn()} />);
    expect(screen.getByText('Idle — plugged in')).toBeInTheDocument();
    expect(screen.getByText('Idle fees are accruing')).toBeInTheDocument();
  });

  it('shows "Idle — plugged in" during the fee-free grace period, without the fee warning', () => {
    // Regression: target reached but idle_minutes is still 0 (within the
    // 30-minute grace period before billable idle time starts) - the badge
    // must switch away from "Charging" immediately, but the fee-accruing
    // subtext should not appear yet since no fees are accruing.
    const graceStatus: ChargingSessionStatus = { ...baseStatus, current_battery_percentage: 80, target_reached: true, idle_minutes: 0, idle_fee: 0 };
    render(<ActiveSessionCard status={graceStatus} onStop={vi.fn()} />);
    expect(screen.getByText('Idle — plugged in')).toBeInTheDocument();
    expect(screen.queryByText('Charging')).not.toBeInTheDocument();
    expect(screen.queryByText('Idle fees are accruing')).not.toBeInTheDocument();
  });

  it('calls onStop when the stop button is clicked', () => {
    const onStop = vi.fn();
    render(<ActiveSessionCard status={baseStatus} onStop={onStop} />);
    fireEvent.click(screen.getByRole('button', { name: 'Stop charging' }));
    expect(onStop).toHaveBeenCalledTimes(1);
  });
});
