-- database/03_seed_data.sql

-- Insert Admin User (password: password)
INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'admin@electra.com',
    '$2b$12$ZsIvRipWywS5lRgIP26EeOxkeRr1mKcAKOs6LLML.D70xL2QkveCG',
    'System Admin',
    '1234567890',
    'Admin',
    10000.00
) ON CONFLICT DO NOTHING;

-- Insert Operator User (password: password)
INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance)
VALUES (
    '22222222-2222-2222-2222-222222222222',
    'operator@electra.com',
    '$2b$12$ZsIvRipWywS5lRgIP26EeOxkeRr1mKcAKOs6LLML.D70xL2QkveCG',
    'Station Operator',
    '0987654321',
    'Operator',
    0.00
) ON CONFLICT DO NOTHING;

-- Insert Company
INSERT INTO COMPANIES (company_id, name)
VALUES (
    '33333333-3333-3333-3333-333333333333',
    'Electra Corp'
) ON CONFLICT DO NOTHING;

-- Link Operator to Company
INSERT INTO COMPANY_OPERATOR_MEMBERSHIPS (company_id, user_id)
VALUES (
    '33333333-3333-3333-3333-333333333333',
    '22222222-2222-2222-2222-222222222222'
) ON CONFLICT DO NOTHING;

-- Insert Area
INSERT INTO AREAS (area_id, name)
VALUES (
    '44444444-4444-4444-4444-444444444444',
    'Downtown Bangalore'
) ON CONFLICT DO NOTHING;

-- Insert Station
INSERT INTO STATIONS (station_id, company_id, area_id, name, gps_coordinates, price_per_kwh, minimum_session_fee, opening_time_local, closing_time_local, timezone)
VALUES (
    '55555555-5555-5555-5555-555555555555',
    '33333333-3333-3333-3333-333333333333',
    '44444444-4444-4444-4444-444444444444',
    'Electra Hub 1',
    ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326),
    15.50,
    50.00,
    '06:00:00',
    '23:00:00',
    'Asia/Kolkata'
) ON CONFLICT DO NOTHING;

-- Insert Charging Ports
INSERT INTO CHARGING_PORTS (port_id, station_id, qr_code, connector_type, charger_type, status)
VALUES (
    '66666666-6666-6666-6666-666666666666',
    '55555555-5555-5555-5555-555555555555',
    'QR_CCS2_001',
    'CCS2',
    'Fast',
    'Available'
) ON CONFLICT DO NOTHING;

INSERT INTO CHARGING_PORTS (port_id, station_id, qr_code, connector_type, charger_type, status)
VALUES (
    '77777777-7777-7777-7777-777777777777',
    '55555555-5555-5555-5555-555555555555',
    'QR_TYPE2_001',
    'Type 2',
    'Level 2',
    'Available'
) ON CONFLICT DO NOTHING;
