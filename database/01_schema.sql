-- 01_schema.sql
-- Create necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- 1. Native ENUMs
CREATE TYPE port_status_enum AS ENUM ('Available', 'Reserved', 'Charging', 'Pending Waitlist', 'Maintenance', 'Offline');
CREATE TYPE reservation_status_enum AS ENUM ('Confirmed', 'Active', 'Expired', 'Cancelled', 'Completed');

-- 2. Core Tables

CREATE TABLE USERS (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    phone_number VARCHAR(20),
    role VARCHAR(50) NOT NULL DEFAULT 'Driver',
    wallet_balance DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    banned_until TIMESTAMP,
    is_suspended BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE VEHICLES (
    vehicle_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE RESTRICT,
    registration_number VARCHAR(50) UNIQUE NOT NULL,
    make VARCHAR(100),
    model VARCHAR(100),
    battery_capacity DECIMAL(5, 2) NOT NULL CHECK (battery_capacity >= 2 AND battery_capacity <= 250),
    connector_type VARCHAR(50) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Partial unique index for default vehicle
CREATE UNIQUE INDEX idx_vehicles_default ON VEHICLES (user_id) WHERE is_default = TRUE;

CREATE TABLE COMPANIES (
    company_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    is_deprecating BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE COMPANY_OPERATOR_MEMBERSHIPS (
    membership_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES COMPANIES(company_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, user_id)
);
CREATE INDEX idx_operator_membership_user ON COMPANY_OPERATOR_MEMBERSHIPS(user_id, company_id, is_active);

CREATE TABLE AREAS (
    area_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE STATIONS (
    station_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES COMPANIES(company_id) ON DELETE RESTRICT,
    area_id UUID REFERENCES AREAS(area_id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    gps_coordinates GEOGRAPHY(Point, 4326) NOT NULL,
    price_per_kwh DECIMAL(10, 2) NOT NULL CHECK (price_per_kwh >= 0),
    minimum_session_fee DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    opening_time_local TIME,
    closing_time_local TIME,
    timezone VARCHAR(50) NOT NULL,
    current_shift_start_utc TIMESTAMP,
    current_shift_end_utc TIMESTAMP,
    locked_gate BOOLEAN NOT NULL DEFAULT FALSE,
    locked_gate_at TIMESTAMP,
    is_deprecating BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_stations_area ON STATIONS(area_id);
CREATE INDEX idx_stations_location ON STATIONS USING GIST(gps_coordinates);
CREATE INDEX idx_stations_company ON STATIONS(company_id);

CREATE TABLE STATION_GATE_EVENTS (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id UUID NOT NULL REFERENCES STATIONS(station_id) ON DELETE CASCADE,
    locked_at TIMESTAMP NOT NULL,
    unlocked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE CHARGING_PORTS (
    port_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id UUID NOT NULL REFERENCES STATIONS(station_id) ON DELETE RESTRICT,
    qr_code VARCHAR(100) UNIQUE NOT NULL,
    connector_type VARCHAR(50) NOT NULL,
    charger_type VARCHAR(50) NOT NULL,
    status port_status_enum NOT NULL DEFAULT 'Available',
    is_pending_maintenance BOOLEAN NOT NULL DEFAULT FALSE,
    has_health_warning BOOLEAN NOT NULL DEFAULT FALSE,
    has_blocked_warning BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_ports_status ON CHARGING_PORTS(status);
CREATE INDEX idx_ports_types ON CHARGING_PORTS(connector_type, charger_type);

CREATE TABLE RESERVATIONS (
    reservation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE RESTRICT,
    vehicle_id UUID NOT NULL REFERENCES VEHICLES(vehicle_id) ON DELETE RESTRICT,
    port_id UUID NOT NULL REFERENCES CHARGING_PORTS(port_id) ON DELETE RESTRICT,
    status reservation_status_enum NOT NULL DEFAULT 'Confirmed',
    is_extended BOOLEAN NOT NULL DEFAULT FALSE,
    is_from_waitlist BOOLEAN NOT NULL DEFAULT FALSE,
    waitlist_joined_at TIMESTAMP,
    cancellation_reason VARCHAR(255),
    status_updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reserved_tariff DECIMAL(10, 2) NOT NULL,
    expires_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '15 minutes'),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_reservations_user ON RESERVATIONS(user_id, status);

CREATE TABLE WAITLIST (
    waitlist_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    station_id UUID NOT NULL REFERENCES STATIONS(station_id) ON DELETE CASCADE,
    vehicle_id UUID NOT NULL REFERENCES VEHICLES(vehicle_id) ON DELETE CASCADE,
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    joined_tariff DECIMAL(10, 2) NOT NULL,
    joined_minimum_fee DECIMAL(10, 2) NOT NULL,
    offered_port_id UUID REFERENCES CHARGING_PORTS(port_id) ON DELETE SET NULL,
    offered_at TIMESTAMP
);
CREATE INDEX idx_waitlist_station ON WAITLIST(station_id);
CREATE INDEX idx_waitlist_offered_port ON WAITLIST(offered_port_id);

CREATE TABLE WAITLIST_REJECTIONS (
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    port_id UUID NOT NULL REFERENCES CHARGING_PORTS(port_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, port_id)
);
CREATE INDEX idx_waitlist_rejections ON WAITLIST_REJECTIONS(user_id, port_id);

CREATE TABLE CHARGING_SESSIONS (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reservation_id UUID NOT NULL REFERENCES RESERVATIONS(reservation_id) ON DELETE RESTRICT,
    initial_battery_percentage DECIMAL(5, 2) NOT NULL CHECK (initial_battery_percentage >= 0 AND initial_battery_percentage <= 100),
    target_battery_percentage DECIMAL(5, 2) NOT NULL CHECK (target_battery_percentage > initial_battery_percentage AND target_battery_percentage <= 100),
    applied_tariff DECIMAL(10, 2) NOT NULL CHECK (applied_tariff >= 0),
    is_overstay_penalized BOOLEAN NOT NULL DEFAULT FALSE,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    idle_start_time TIMESTAMP,
    end_time TIMESTAMP,
    cumulative_closure_seconds INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_sessions_active ON CHARGING_SESSIONS(end_time) WHERE end_time IS NULL;

CREATE TABLE INVOICES (
    invoice_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    charging_session_id UUID UNIQUE NOT NULL REFERENCES CHARGING_SESSIONS(session_id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE RESTRICT,
    total_amount DECIMAL(10, 2) NOT NULL CHECK (total_amount >= 0),
    is_paid BOOLEAN NOT NULL DEFAULT FALSE,
    paid_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE FAVORITES (
    favorite_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    station_id UUID NOT NULL REFERENCES STATIONS(station_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, station_id)
);

CREATE TABLE RATINGS (
    rating_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    station_id UUID NOT NULL REFERENCES STATIONS(station_id) ON DELETE CASCADE,
    overall_score INTEGER NOT NULL CHECK (overall_score BETWEEN 1 AND 5),
    cleanliness_score INTEGER NOT NULL CHECK (cleanliness_score BETWEEN 1 AND 5),
    access_score INTEGER NOT NULL CHECK (access_score BETWEEN 1 AND 5),
    experience_score INTEGER NOT NULL CHECK (experience_score BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, station_id)
);

CREATE TABLE NOTIFICATIONS (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE SEARCH_HISTORY (
    search_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    search_query VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE PENALTIES (
    penalty_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    reason VARCHAR(255) NOT NULL,
    points INTEGER NOT NULL DEFAULT 1,
    is_served BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_penalties_user_unserved ON PENALTIES(user_id, is_served);

CREATE TABLE MAINTENANCE_SCHEDULES (
    maintenance_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    port_id UUID NOT NULL REFERENCES CHARGING_PORTS(port_id) ON DELETE CASCADE,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Scheduled',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE AUDIT_LOGS (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID, -- Can be null for system actions
    action VARCHAR(255) NOT NULL,
    entity_type VARCHAR(255),
    entity_id UUID,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE SYSTEM_SETTINGS (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE FAULT_EXEMPTION_CLAIMS (
    claim_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    waitlist_id UUID,
    port_id UUID NOT NULL REFERENCES CHARGING_PORTS(port_id) ON DELETE CASCADE,
    claimed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_fault_exemption_user_time ON FAULT_EXEMPTION_CLAIMS(user_id, claimed_at);
-- Phase 3.5: Internal Wallet Ledger System
CREATE TABLE PAYMENT_METHODS (
    payment_method_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    card_last4 VARCHAR(4) NOT NULL,
    expiry_month INT NOT NULL,
    expiry_year INT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE WALLET_TRANSACTIONS (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- 'Top-Up', 'Escrow Hold', 'Escrow Release', 'Session Payment', 'Penalty', 'Welcome Bonus'
    reference_id UUID, -- Can link to reservation_id, session_id, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE RECENT_STATIONS (
    recent_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES USERS(user_id) ON DELETE CASCADE,
    station_id UUID NOT NULL REFERENCES STATIONS(station_id) ON DELETE CASCADE,
    viewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- Trigger to maintain USERS.wallet_balance exactly equal to sum of WALLET_TRANSACTIONS
CREATE OR REPLACE FUNCTION update_wallet_balance_from_transactions()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        UPDATE USERS
        SET wallet_balance = (
            SELECT COALESCE(SUM(amount), 0)
            FROM WALLET_TRANSACTIONS
            WHERE user_id = OLD.user_id
        )
        WHERE user_id = OLD.user_id;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE USERS SET wallet_balance = (SELECT COALESCE(SUM(amount), 0) FROM WALLET_TRANSACTIONS WHERE user_id = OLD.user_id) WHERE user_id = OLD.user_id;
        IF NEW.user_id != OLD.user_id THEN
            UPDATE USERS SET wallet_balance = (SELECT COALESCE(SUM(amount), 0) FROM WALLET_TRANSACTIONS WHERE user_id = NEW.user_id) WHERE user_id = NEW.user_id;
        END IF;
        RETURN NEW;
    ELSE -- INSERT
        UPDATE USERS
        SET wallet_balance = (
            SELECT COALESCE(SUM(amount), 0)
            FROM WALLET_TRANSACTIONS
            WHERE user_id = NEW.user_id
        )
        WHERE user_id = NEW.user_id;
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_wallet_balance
AFTER INSERT OR UPDATE OR DELETE ON WALLET_TRANSACTIONS
FOR EACH ROW EXECUTE FUNCTION update_wallet_balance_from_transactions();
