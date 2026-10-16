import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Login from './Login';
import { authService } from '../services/api';
import { useAuth } from '../context/auth-context';
import '../test/setup';

vi.mock('../services/api', () => ({ authService: { login: vi.fn() } }));
vi.mock('../context/auth-context', () => ({ useAuth: vi.fn() }));

describe('Login', () => {
  const login = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useAuth).mockReturnValue({ token: null, isAuthenticated: false, user: null, isLoading: false, login, logout: vi.fn(), fetchUser: vi.fn(), refreshUser: vi.fn() });
  });

  it('preserves the email/password login contract and hydrates auth with the returned token', async () => {
    vi.mocked(authService.login).mockResolvedValue({ access_token: 'jwt-token', token_type: 'bearer' });
    render(<MemoryRouter><Login /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: ' driver@example.com ' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'securepass' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));

    await waitFor(() => expect(authService.login).toHaveBeenCalledWith('driver@example.com', 'securepass'));
    expect(login).toHaveBeenCalledWith('jwt-token');
  });

  it('keeps backend authentication errors visible', async () => {
    vi.mocked(authService.login).mockRejectedValue(new Error('Incorrect email or password'));
    render(<MemoryRouter><Login /></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'driver@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrongpass' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument();
  });
});
