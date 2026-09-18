export type UserRole = 'Driver' | 'Operator' | 'Admin';

export interface User {
  id: string;
  user_id?: string;
  email: string;
  full_name?: string;
  phone_number?: string;
  role: UserRole;
  is_suspended: boolean;
  is_active?: boolean;
  wallet_balance: number;
  banned_until?: string | null;
  created_at: string;
}

export type ConnectorType = 'Type2' | 'Type 2' | 'CCS2' | 'CCS1' | 'CHAdeMO';

export interface Vehicle {
  id?: string;
  vehicle_id: string;
  user_id: string;
  make?: string;
  model?: string;
  license_plate: string;
  battery_capacity_kwh: number;
  connector_type: ConnectorType;
  is_default: boolean;
  is_active?: boolean;
  created_at: string;
  updated_at?: string;
}

export interface ChargingPort {
  port_id: string;
  station_id: string;
  qr_code: string;
  connector_type: string;
  charger_type: string;
  status: string;
  is_pending_maintenance: boolean;
  has_health_warning: boolean;
  has_blocked_warning: boolean;
  is_active: boolean;
  status_updated_at: string;
  created_at: string;
}

export interface Station {
  station_id: string;
  company_id: string;
  area_id?: string | null;
  name: string;
  price_per_kwh: number;
  minimum_session_fee: number;
  timezone: string;
  opening_time_local?: string | null;
  closing_time_local?: string | null;
  locked_gate: boolean;
  is_deprecating: boolean;
  is_active: boolean;
  created_at: string;
  lat: number;
  lng: number;
  ports: ChargingPort[];
}

export interface Favorite {
  favorite_id: string;
  station_id: string;
  station: Station;
  created_at: string;
}

export interface Reservation {
  reservation_id: string;
  user_id: string;
  vehicle_id: string;
  port_id: string;
  status: string;
  reserved_tariff: number;
  expires_at: string;
  created_at: string;
}

export interface ChargingSessionStatus {
  session_id: string;
  reservation_id: string;
  port_id: string;
  vehicle_id: string;
  initial_battery_percentage: number;
  target_battery_percentage: number;
  applied_tariff: number;
  start_time: string;
  current_battery_percentage: number;
  target_reached: boolean;
  energy_delivered_kwh: number;
  energy_cost: number;
  idle_minutes: number;
  idle_fee: number;
  total_cost: number;
  elapsed_minutes: number;
  eta_minutes_remaining: number;
}

export interface Invoice {
  invoice_id: string;
  charging_session_id: string;
  user_id: string;
  total_amount: number;
  is_paid: boolean;
  paid_at?: string | null;
  created_at: string;
}

export interface WaitlistStatus {
  waitlist_id: string;
  station_id: string;
  vehicle_id: string;
  joined_at: string;
  joined_tariff: number;
  joined_minimum_fee: number;
  position: number;
  offered_port_id?: string | null;
  offered_at?: string | null;
  offer_expires_at?: string | null;
}

export interface WalletTransaction {
  transaction_id: string;
  amount: number;
  transaction_type: string;
  reference_id?: string | null;
  created_at: string;
}

export interface PaymentMethod {
  payment_method_id: string;
  card_last4: string;
  expiry_month: number;
  expiry_year: number;
  is_default: boolean;
  created_at: string;
}

export interface Company {
  company_id: string;
  name: string;
  is_deprecating: boolean;
  is_active: boolean;
  created_at: string;
}

export interface CompanyMembership {
  membership_id: string;
  company_id: string;
  user_id: string;
  is_active: boolean;
  assigned_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface DriverDashboardData {
  active_sessions?: number | string;
  upcoming_bookings?: number | string;
  unpaid_invoices?: number | string;
  energy_charged_kwh?: number;
  recent_activity?: Array<{ id: string; location: string; date: string; amount: string; status: string }>;
}

export interface RevenueByDay {
  date: string;
  revenue: number;
}

export interface AdminReport {
  total_users: number;
  total_companies: number;
  total_stations: number;
  revenue_by_day: RevenueByDay[];
  system_activity_24h: number;
  top_actions: Array<{ action: string; count: number }>;
  active_sessions: number;
  reservations_today: number;
  most_popular_stations: Array<{ station_id: string; name: string; session_count: number }>;
}

export interface OperatorReport {
  todays_reservations: number;
  active_sessions: number;
  revenue: number;
  revenue_by_day: RevenueByDay[];
  charger_utilization_pct: number;
  maintenance_alerts: number;
  peak_hours: Array<{ hour: number; count: number }>;
  queue_statistics: Array<{ station_id: string; name: string; queue_length: number }>;
}

export interface Notification {
  notification_id: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface Rating {
  rating_id: string;
  user_id: string;
  station_id: string;
  overall_score: number;
  cleanliness_score: number;
  access_score: number;
  experience_score: number;
  comment?: string | null;
  created_at: string;
}

export interface StationRatingSummary {
  rating_count: number;
  average_overall: number | null;
  average_cleanliness: number | null;
  average_access: number | null;
  average_experience: number | null;
}

export interface StationRatingsResponse {
  summary: StationRatingSummary;
  ratings: Rating[];
  my_rating: Rating | null;
}

export interface SearchHistoryEntry {
  search_id: string;
  lat: number;
  lng: number;
  radius_km: number;
  connector_type?: string | null;
  min_power_kw?: number | null;
  created_at: string;
}

export interface MaintenanceSchedule {
  maintenance_id: string;
  port_id: string;
  start_time: string;
  end_time: string;
  status: string;
  created_at: string;
}
