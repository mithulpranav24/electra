import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type {
  AuthResponse,
  ChargingPort,
  Company,
  CompanyMembership,
  DriverDashboardData,
  Favorite,
  PaymentMethod,
  Reservation,
  Station,
  User,
  Vehicle,
  WalletTransaction,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export const api = axios.create({ baseURL: API_BASE_URL });

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === 'object' && 'success' in response.data && response.data.success) {
      response.data = response.data.data;
    }
    return response;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth-unauthorized'));
    }
    if (error.response?.data && typeof error.response.data === 'object' && 'message' in error.response.data) {
      error.message = String(error.response.data.message);
    }
    return Promise.reject(error);
  },
);

export const authService = {
  login: async (email: string, password: string): Promise<AuthResponse> => {
    const formData = new URLSearchParams({ username: email, password });
    const { data } = await api.post<AuthResponse>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return data;
  },
  register: async (payload: { email: string; password: string; full_name?: string }): Promise<User> => {
    const { data } = await api.post<User>('/auth/register', payload);
    return data;
  },
  getCurrentUser: async (): Promise<User> => {
    const { data } = await api.get<User>('/users/me');
    return data;
  },
  getMyCompanies: async (): Promise<CompanyMembership[]> => {
    const { data } = await api.get<CompanyMembership[]>('/users/me/companies');
    return data;
  },
  getDashboardData: async (): Promise<DriverDashboardData> => {
    const { data } = await api.get<DriverDashboardData>('/users/me/dashboard');
    return data;
  },
  updateProfile: async (userData: Partial<Pick<User, 'full_name' | 'phone_number'>>): Promise<User> => {
    const { data } = await api.put<User>('/users/me', userData);
    return data;
  },
  updatePassword: async (oldPassword: string, newPassword: string): Promise<void> => {
    await api.put('/users/me/password', { old_password: oldPassword, new_password: newPassword });
  },
  deleteAccount: async (): Promise<void> => {
    await api.delete('/users/me');
  },
  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },
};

export type VehiclePayload = Pick<Vehicle, 'make' | 'model' | 'license_plate' | 'battery_capacity_kwh' | 'connector_type'>;

export const vehicleService = {
  getVehicles: async (): Promise<Vehicle[]> => {
    const { data } = await api.get<Vehicle[]>('/vehicles', { params: { _t: Date.now() } });
    return data;
  },
  createVehicle: async (vehicleData: VehiclePayload): Promise<Vehicle> => {
    const { data } = await api.post<Vehicle>('/vehicles', vehicleData);
    return data;
  },
  updateVehicle: async (id: string, vehicleData: Partial<VehiclePayload>): Promise<Vehicle> => {
    const { data } = await api.put<Vehicle>(`/vehicles/${id}`, vehicleData);
    return data;
  },
  deleteVehicle: async (id: string): Promise<void> => {
    await api.delete(`/vehicles/${id}`);
  },
  setDefaultVehicle: async (id: string): Promise<Vehicle> => {
    const { data } = await api.post<Vehicle>(`/vehicles/${id}/default`);
    return data;
  },
};

export const walletService = {
  getBalance: async (): Promise<number> => {
    const { data } = await api.get<{ balance: number }>('/wallet/balance');
    return Number(data.balance);
  },
  getTransactions: async (): Promise<WalletTransaction[]> => {
    const { data } = await api.get<WalletTransaction[]>('/wallet/transactions');
    return data;
  },
  getPaymentMethods: async (): Promise<PaymentMethod[]> => {
    const { data } = await api.get<PaymentMethod[]>('/wallet/payment-methods');
    return data;
  },
  topUp: async (amount: number): Promise<WalletTransaction> => {
    const { data } = await api.post<WalletTransaction>('/wallet/topup', { amount });
    return data;
  },
};

export const adminService = {
  getCompanies: async (): Promise<Company[]> => {
    const { data } = await api.get<Company[]>('/admin/companies');
    return data;
  },
  createCompany: async (companyData: { name: string }): Promise<Company> => {
    const { data } = await api.post<Company>('/admin/companies', companyData);
    return data;
  },
  updateCompany: async (id: string, companyData: Partial<Pick<Company, 'name' | 'is_active' | 'is_deprecating'>>): Promise<Company> => {
    const { data } = await api.put<Company>(`/admin/companies/${id}`, companyData);
    return data;
  },
  getOperators: async (companyId: string): Promise<CompanyMembership[]> => {
    const { data } = await api.get<CompanyMembership[]>(`/admin/companies/${companyId}/memberships`);
    return data;
  },
  assignOperator: async (companyId: string, userId: string): Promise<CompanyMembership> => {
    const { data } = await api.post<CompanyMembership>('/admin/companies/memberships', { company_id: companyId, user_id: userId });
    return data;
  },
};

export interface StationPayload {
  name: string;
  price_per_kwh: number;
  minimum_session_fee: number;
  timezone: string;
  opening_time_local?: string | null;
  closing_time_local?: string | null;
  locked_gate?: boolean;
  lat: number;
  lng: number;
}

export interface PortPayload {
  qr_code: string;
  connector_type: string;
  charger_type: string;
  status?: string;
  is_pending_maintenance?: boolean;
  has_health_warning?: boolean;
  has_blocked_warning?: boolean;
  is_active?: boolean;
}

export const operatorService = {
  getStations: async (companyId: string): Promise<Station[]> => {
    const { data } = await api.get<Station[]>(`/operator/stations/company/${companyId}`);
    return data;
  },
  createStation: async (companyId: string, stationData: StationPayload): Promise<Station> => {
    const { data } = await api.post<Station>(`/operator/stations/company/${companyId}`, stationData);
    return data;
  },
  updateStation: async (id: string, stationData: Partial<StationPayload>): Promise<Station> => {
    const { data } = await api.put<Station>(`/operator/stations/${id}`, stationData);
    return data;
  },
  deleteStation: async (id: string): Promise<void> => {
    await api.delete(`/operator/stations/${id}`);
  },
  createPort: async (stationId: string, portData: PortPayload): Promise<ChargingPort> => {
    const { data } = await api.post<ChargingPort>(`/operator/stations/${stationId}/ports`, portData);
    return data;
  },
  updatePort: async (portId: string, portData: Partial<PortPayload>): Promise<ChargingPort> => {
    const { data } = await api.put<ChargingPort>(`/operator/stations/ports/${portId}`, portData);
    return data;
  },
  deletePort: async (portId: string): Promise<void> => {
    await api.delete(`/operator/stations/ports/${portId}`);
  },
};

export interface StationSearchPayload {
  lat: number;
  lng: number;
  radius_km: number;
  connector_type: string | null;
  min_power_kw: number | null;
}

export const searchService = {
  searchStations: async (payload: StationSearchPayload): Promise<Station[]> => {
    const { data } = await api.post<Station[]>('/search/stations', payload);
    return Array.isArray(data) ? data : [];
  },
  getStation: async (id: string): Promise<Station> => {
    const { data } = await api.get<Station>(`/search/stations/${id}`);
    return data;
  },
  getRecentStations: async (): Promise<Station[]> => {
    const { data } = await api.get<Station[]>('/search/recent');
    return data;
  },
};

export const favoriteService = {
  getFavorites: async (): Promise<Favorite[]> => {
    const { data } = await api.get<Favorite[]>('/favorites');
    return data;
  },
  addFavorite: async (stationId: string): Promise<void> => {
    await api.post(`/favorites/${stationId}`);
  },
  removeFavorite: async (stationId: string): Promise<void> => {
    await api.delete(`/favorites/${stationId}`);
  },
};

export const reservationService = {
  getActive: async (): Promise<Reservation[]> => {
    const { data } = await api.get<Reservation[]>('/reservations/active');
    return data;
  },
  create: async (payload: { vehicle_id: string; port_id?: string; station_id?: string }): Promise<Reservation> => {
    const { data } = await api.post<Reservation>('/reservations', payload);
    return data;
  },
  cancel: async (reservationId: string): Promise<{ message?: string }> => {
    const { data } = await api.post<{ message?: string }>(`/reservations/${reservationId}/cancel`);
    return data;
  },
};
