export interface User {
  id: string;
  email: string;
  full_name: string;
  phone_number?: string;
  role: 'Driver' | 'Operator' | 'Admin';
  is_suspended: boolean;
  wallet_balance: number;
  created_at: string;
}

export interface Vehicle {
  id?: string;
  vehicle_id: string;
  user_id: string;
  make: string;
  model: string;
  license_plate: string;
  battery_capacity_kwh: number;
  connector_type: 'Type2' | 'CCS2' | 'CHAdeMO';
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}
