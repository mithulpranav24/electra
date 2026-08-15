import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { ChargingPort, Vehicle } from '../types';
import { ReservationModal } from './ReservationModal';
import '../test/setup';

const port: ChargingPort = {
  port_id: 'port-1', station_id: 'station-1', qr_code: 'QR-1', connector_type: 'CCS2', charger_type: 'DC Fast', status: 'Available',
  is_pending_maintenance: false, has_health_warning: false, has_blocked_warning: false, is_active: true,
  status_updated_at: '2026-08-15T12:00:00Z', created_at: '2026-08-15T12:00:00Z',
};

const vehicle: Vehicle = {
  vehicle_id: 'vehicle-1', user_id: 'user-1', make: 'Tata', model: 'Nexon EV', license_plate: 'KA01AB1234',
  battery_capacity_kwh: 40.5, connector_type: 'CCS2', is_default: true, created_at: '2026-08-15T12:00:00Z',
};

function renderModal(overrides: Partial<React.ComponentProps<typeof ReservationModal>> = {}) {
  const props: React.ComponentProps<typeof ReservationModal> = {
    open: true,
    onClose: vi.fn(),
    onConfirm: vi.fn(),
    stationName: 'Indiranagar Hub',
    port,
    pricePerKwh: 12,
    vehicles: [vehicle],
    selectedVehicleId: 'vehicle-1',
    onVehicleChange: vi.fn(),
    walletBalance: 1500,
    ...overrides,
  };
  render(<MemoryRouter><ReservationModal {...props} /></MemoryRouter>);
  return props;
}

describe('ReservationModal', () => {
  it('blocks reservation when the escrow cannot be covered', () => {
    renderModal({ walletBalance: 999 });
    expect(screen.getByText('Wallet balance is too low')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reserve this port' })).toBeDisabled();
  });

  it('explains the compatible-vehicle requirement', () => {
    renderModal({ vehicles: [], selectedVehicleId: '' });
    expect(screen.getByText('No compatible vehicle')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to vehicles' })).toHaveAttribute('href', '/driver/vehicles');
  });

  it('submits a valid reviewed reservation', () => {
    const props = renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'Reserve this port' }));
    expect(props.onConfirm).toHaveBeenCalledTimes(1);
  });
});
