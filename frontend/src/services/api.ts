import axios from 'axios';
import type { InternalAxiosRequestConfig, AxiosError } from 'axios';
import type { User, Vehicle } from '../types';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth-unauthorized'));
    }
    return Promise.reject(error);
  }
);

export const authService = {
  getCurrentUser: async (): Promise<User> => {
    const { data } = await api.get('/users/me');
    return data;
  },
  updateProfile: async (userData: Partial<User>): Promise<User> => {
    const { data } = await api.put('/users/me', userData);
    return data;
  },
  deleteAccount: async (): Promise<void> => {
    await api.delete('/users/me');
  },
};

export const vehicleService = {
  getVehicles: async (): Promise<Vehicle[]> => {
    const { data } = await api.get('/vehicles');
    return data;
  },
  
  createVehicle: async (vehicleData: Partial<Vehicle>): Promise<Vehicle> => {
    const { data } = await api.post('/vehicles', vehicleData);
    return data;
  },

  updateVehicle: async (id: string, vehicleData: Partial<Vehicle>): Promise<Vehicle> => {
    const { data } = await api.put(`/vehicles/${id}`, vehicleData);
    return data;
  },

  deleteVehicle: async (id: string): Promise<void> => {
    await api.delete(`/vehicles/${id}`);
  },

  setDefaultVehicle: async (id: string): Promise<Vehicle> => {
    const { data } = await api.post(`/vehicles/${id}/default`);
    return data;
  },
};
