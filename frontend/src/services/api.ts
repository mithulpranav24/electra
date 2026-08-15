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
  (response) => {
    // Unwrap the unified JSON response if it exists
    if (response.data && typeof response.data === 'object' && 'success' in response.data) {
      if (response.data.success) {
        // Replace the response data with the nested data
        response.data = response.data.data;
      }
    }
    return response;
  },
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth-unauthorized'));
    }
    
    // Attempt to parse the unified JSON error structure
    if (error.response?.data && typeof error.response.data === 'object' && 'message' in error.response.data) {
      const data = error.response.data as { message: string };
      error.message = data.message;
    }
    
    return Promise.reject(error);
  }
);


export const authService = {
  getCurrentUser: async (): Promise<User> => {
    const { data } = await api.get('/users/me');
    return data;
  },
  getMyCompanies: async (): Promise<any[]> => {
    const { data } = await api.get('/users/me/companies');
    return data;
  },
  getDashboardData: async (): Promise<any> => {
    const { data } = await api.get('/users/me/dashboard');
    return data;
  },
  updateProfile: async (userData: Partial<User>): Promise<User> => {

    const { data } = await api.put('/users/me', userData);
    return data;
  },
  deleteAccount: async (): Promise<void> => {
    await api.delete('/users/me');
  },
  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },
};

export const vehicleService = {
  getVehicles: async (): Promise<Vehicle[]> => {
    // Use cache buster to prevent browser from returning stale data after setting default
    const { data } = await api.get('/vehicles', {
      params: { _t: new Date().getTime() }
    });
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

export const adminService = {
  getCompanies: async (): Promise<any[]> => {
    const { data } = await api.get('/admin/companies');
    return data;
  },
  createCompany: async (companyData: any): Promise<any> => {
    const { data } = await api.post('/admin/companies', companyData);
    return data;
  },
  updateCompany: async (id: string, companyData: any): Promise<any> => {
    const { data } = await api.put(`/admin/companies/${id}`, companyData);
    return data;
  },
  getOperators: async (companyId: string): Promise<any[]> => {
    const { data } = await api.get(`/admin/companies/${companyId}/memberships`);
    return data;
  },
  assignOperator: async (companyId: string, userId: string): Promise<any> => {
    const { data } = await api.post('/admin/companies/memberships', { company_id: companyId, user_id: userId });
    return data;
  }
};

export const operatorService = {
  getStations: async (companyId: string): Promise<any[]> => {
    const { data } = await api.get(`/operator/stations/company/${companyId}`);
    return data;
  },
  createStation: async (companyId: string, stationData: any): Promise<any> => {
    const { data } = await api.post(`/operator/stations/company/${companyId}`, stationData);
    return data;
  },
  updateStation: async (id: string, stationData: any): Promise<any> => {
    const { data } = await api.put(`/operator/stations/${id}`, stationData);
    return data;
  },
  deleteStation: async (id: string): Promise<void> => {
    await api.delete(`/operator/stations/${id}`);
  },
  createPort: async (stationId: string, portData: any): Promise<any> => {
    const { data } = await api.post(`/operator/stations/${stationId}/ports`, portData);
    return data;
  },
  updatePort: async (portId: string, portData: any): Promise<any> => {
    const { data } = await api.put(`/operator/stations/ports/${portId}`, portData);
    return data;
  },
  deletePort: async (portId: string): Promise<void> => {
    await api.delete(`/operator/stations/ports/${portId}`);
  }
};

export const searchService = {
  getRecentStations: async (): Promise<any[]> => {
    const { data } = await api.get('/search/recent');
    return data;
  }
};

export const favoriteService = {
  getFavorites: async (): Promise<any[]> => {
    const { data } = await api.get('/favorites');
    return data;
  },
  addFavorite: async (stationId: string): Promise<any> => {
    const { data } = await api.post(`/favorites/${stationId}`);
    return data;
  },
  removeFavorite: async (stationId: string): Promise<any> => {
    const { data } = await api.delete(`/favorites/${stationId}`);
    return data;
  }
};
