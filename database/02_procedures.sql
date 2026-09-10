-- 02_procedures.sql

-- ==========================================
-- 1. IMMUTABILITY TRIGGERS
-- ==========================================

CREATE OR REPLACE FUNCTION trg_enforce_immutability()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_TABLE_NAME = 'audit_logs' THEN
        RAISE EXCEPTION 'AUDIT_LOGS records are immutable.';
    END IF;

    IF TG_TABLE_NAME = 'charging_sessions' THEN
        IF TG_OP = 'DELETE' THEN
            IF OLD.end_time IS NOT NULL THEN
                RAISE EXCEPTION 'Completed CHARGING_SESSIONS cannot be deleted.';
            END IF;
        ELSIF TG_OP = 'UPDATE' THEN
            IF OLD.end_time IS NOT NULL THEN
                RAISE EXCEPTION 'Completed CHARGING_SESSIONS cannot be modified.';
            END IF;
        END IF;
    END IF;

    IF TG_TABLE_NAME = 'invoices' THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'INVOICES cannot be deleted.';
        ELSIF TG_OP = 'UPDATE' THEN
            -- Only allow updates to is_paid and paid_at if it's currently unpaid
            IF OLD.is_paid = TRUE THEN
                RAISE EXCEPTION 'Paid INVOICES cannot be modified.';
            END IF;
            
            -- Ensure no other fields were modified
            IF NEW.invoice_id != OLD.invoice_id OR 
               NEW.charging_session_id != OLD.charging_session_id OR 
               NEW.user_id != OLD.user_id OR 
               NEW.total_amount != OLD.total_amount OR 
               NEW.created_at != OLD.created_at THEN
                RAISE EXCEPTION 'Only is_paid and paid_at can be updated on INVOICES.';
            END IF;
        END IF;
    END IF;

    -- A BEFORE DELETE trigger has no NEW row (it's NULL); returning NEW here
    -- unconditionally would silently cancel every DELETE this function doesn't
    -- explicitly RAISE EXCEPTION on (e.g. an incomplete, not-yet-ended
    -- CHARGING_SESSIONS row), since Postgres treats a NULL return as "skip
    -- this row" rather than "no objection." Must return OLD for DELETE.
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_immutability
BEFORE UPDATE OR DELETE ON AUDIT_LOGS
FOR EACH ROW EXECUTE FUNCTION trg_enforce_immutability();

CREATE TRIGGER trg_charging_sessions_immutability
BEFORE UPDATE OR DELETE ON CHARGING_SESSIONS
FOR EACH ROW EXECUTE FUNCTION trg_enforce_immutability();

CREATE TRIGGER trg_invoices_immutability
BEFORE UPDATE OR DELETE ON INVOICES
FOR EACH ROW EXECUTE FUNCTION trg_enforce_immutability();


-- ==========================================
-- 2. SOFT-DELETE VALIDATION TRIGGERS
-- ==========================================

CREATE OR REPLACE FUNCTION trg_prevent_invalid_soft_delete()
RETURNS TRIGGER AS $$
DECLARE
    active_reservations_count INT;
    active_sessions_count INT;
    pending_waitlist_ports_count INT;
    unpaid_invoices_count INT;
BEGIN
    -- Only trigger when is_active is being flipped to FALSE
    IF OLD.is_active = TRUE AND NEW.is_active = FALSE THEN
        
        -- Check USERS
        IF TG_TABLE_NAME = 'users' THEN
            IF OLD.banned_until IS NOT NULL AND OLD.banned_until > CURRENT_TIMESTAMP THEN
                RAISE EXCEPTION 'Cannot soft-delete banned user.';
            END IF;
            
            SELECT COUNT(*) INTO active_reservations_count FROM RESERVATIONS WHERE user_id = OLD.user_id AND status IN ('Confirmed', 'Active');
            IF active_reservations_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete user with active reservations.'; END IF;

            SELECT COUNT(*) INTO unpaid_invoices_count FROM INVOICES WHERE user_id = OLD.user_id AND is_paid = FALSE;
            IF unpaid_invoices_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete user with unpaid invoices.'; END IF;
        END IF;

        -- Check VEHICLES
        IF TG_TABLE_NAME = 'vehicles' THEN
            SELECT COUNT(*) INTO active_reservations_count FROM RESERVATIONS WHERE vehicle_id = OLD.vehicle_id AND status IN ('Confirmed', 'Active');
            IF active_reservations_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete vehicle with active reservations.'; END IF;
        END IF;

        -- Check CHARGING_PORTS
        IF TG_TABLE_NAME = 'charging_ports' THEN
            IF OLD.status IN ('Reserved', 'Charging', 'Pending Waitlist') THEN
                RAISE EXCEPTION 'Cannot soft-delete charging port in state: %', OLD.status;
            END IF;
        END IF;

        -- Check STATIONS
        IF TG_TABLE_NAME = 'stations' THEN
            SELECT COUNT(*) INTO active_reservations_count FROM RESERVATIONS r JOIN CHARGING_PORTS p ON r.port_id = p.port_id WHERE p.station_id = OLD.station_id AND r.status IN ('Confirmed', 'Active');
            IF active_reservations_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete station with active reservations.'; END IF;
            
            SELECT COUNT(*) INTO pending_waitlist_ports_count FROM CHARGING_PORTS WHERE station_id = OLD.station_id AND status = 'Pending Waitlist';
            IF pending_waitlist_ports_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete station with pending waitlist ports.'; END IF;
        END IF;

        -- Check COMPANIES
        IF TG_TABLE_NAME = 'companies' THEN
            SELECT COUNT(*) INTO active_reservations_count FROM RESERVATIONS r JOIN CHARGING_PORTS p ON r.port_id = p.port_id JOIN STATIONS s ON p.station_id = s.station_id WHERE s.company_id = OLD.company_id AND r.status IN ('Confirmed', 'Active');
            IF active_reservations_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete company with active reservations.'; END IF;
            
            SELECT COUNT(*) INTO pending_waitlist_ports_count FROM CHARGING_PORTS p JOIN STATIONS s ON p.station_id = s.station_id WHERE s.company_id = OLD.company_id AND p.status = 'Pending Waitlist';
            IF pending_waitlist_ports_count > 0 THEN RAISE EXCEPTION 'Cannot soft-delete company with pending waitlist ports.'; END IF;
        END IF;

    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_soft_delete BEFORE UPDATE ON USERS FOR EACH ROW EXECUTE FUNCTION trg_prevent_invalid_soft_delete();
CREATE TRIGGER trg_vehicles_soft_delete BEFORE UPDATE ON VEHICLES FOR EACH ROW EXECUTE FUNCTION trg_prevent_invalid_soft_delete();
CREATE TRIGGER trg_companies_soft_delete BEFORE UPDATE ON COMPANIES FOR EACH ROW EXECUTE FUNCTION trg_prevent_invalid_soft_delete();
CREATE TRIGGER trg_stations_soft_delete BEFORE UPDATE ON STATIONS FOR EACH ROW EXECUTE FUNCTION trg_prevent_invalid_soft_delete();
CREATE TRIGGER trg_ports_soft_delete BEFORE UPDATE ON CHARGING_PORTS FOR EACH ROW EXECUTE FUNCTION trg_prevent_invalid_soft_delete();

-- ==========================================
-- 1.5 WALLET BALANCE MAINTENANCE (ACID compliance for wallet_balance,
-- Phase 3.5). USERS.wallet_balance is a derived cache, not a source of
-- truth: it is always recalculated as SUM(WALLET_TRANSACTIONS.amount) for
-- the user, so every escrow hold/release, payment, refund, and penalty
-- MUST be recorded as a WALLET_TRANSACTIONS row rather than writing
-- wallet_balance directly - a direct UPDATE ... SET wallet_balance = ...
-- is silently discarded the next time any transaction row for that user
-- is inserted, updated, or deleted.
-- ==========================================

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

-- ==========================================
-- 3. STORED PROCEDURES
-- ==========================================

CREATE OR REPLACE PROCEDURE sp_CreateReservation(
    p_user_id UUID,
    p_port_id UUID,
    p_vehicle_id UUID,
    p_grace_period_minutes INT,
    p_cooldown_minutes INT,
    p_ip_address VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id UUID;
    v_station_id UUID;
    v_port_status port_status_enum;
    v_port_connector_type VARCHAR;
    v_port_is_active BOOLEAN;
    v_vehicle_user_id UUID;
    v_vehicle_connector_type VARCHAR;
    v_vehicle_is_active BOOLEAN;
    v_user_wallet_balance DECIMAL;
    v_user_banned_until TIMESTAMP;
    v_user_is_active BOOLEAN;
    v_user_is_suspended BOOLEAN;
    v_station_minimum_fee DECIMAL;
    v_station_price_per_kwh DECIMAL;
    v_station_is_active BOOLEAN;
    v_company_is_active BOOLEAN;
    v_company_is_deprecating BOOLEAN;
    v_station_shift_start TIMESTAMP;
    v_station_shift_end TIMESTAMP;
    v_active_reservations INT;
    v_active_sessions INT;
    v_unpaid_invoices INT;
    v_waitlist_offer INT;
    v_deleted_waitlist_row WAITLIST%ROWTYPE;
    v_new_reservation_id UUID;
BEGIN
    -- Tier 1: Companies > Stations
    SELECT s.company_id, s.station_id INTO v_company_id, v_station_id
    FROM CHARGING_PORTS p
    JOIN STATIONS s ON p.station_id = s.station_id
    WHERE p.port_id = p_port_id;

    IF NOT FOUND THEN RAISE EXCEPTION 'Port not found'; END IF;

    SELECT is_active, is_deprecating INTO v_company_is_active, v_company_is_deprecating 
    FROM COMPANIES WHERE company_id = v_company_id FOR SHARE;

    SELECT is_active, minimum_session_fee, price_per_kwh, current_shift_start_utc, current_shift_end_utc
    INTO v_station_is_active, v_station_minimum_fee, v_station_price_per_kwh, v_station_shift_start, v_station_shift_end
    FROM STATIONS WHERE station_id = v_station_id FOR SHARE;

    -- Tier 2: Charging Ports
    SELECT status, connector_type, is_active INTO v_port_status, v_port_connector_type, v_port_is_active 
    FROM CHARGING_PORTS WHERE port_id = p_port_id FOR UPDATE;

    -- Tier 2.5: Vehicles
    SELECT user_id, connector_type, is_active INTO v_vehicle_user_id, v_vehicle_connector_type, v_vehicle_is_active
    FROM VEHICLES WHERE vehicle_id = p_vehicle_id FOR SHARE;

    -- Tier 3: Users
    SELECT wallet_balance, banned_until, is_active, is_suspended INTO v_user_wallet_balance, v_user_banned_until, v_user_is_active, v_user_is_suspended
    FROM USERS WHERE user_id = p_user_id FOR UPDATE;

    -- Validations
    IF v_port_status != 'Available' THEN RAISE EXCEPTION 'Port is not Available'; END IF;
    IF v_company_is_active = FALSE OR v_company_is_deprecating = TRUE THEN RAISE EXCEPTION 'Company is inactive or deprecating'; END IF;
    IF v_station_is_active = FALSE THEN RAISE EXCEPTION 'Station is inactive'; END IF;
    IF v_port_is_active = FALSE THEN RAISE EXCEPTION 'Port is inactive'; END IF;
    IF v_vehicle_is_active = FALSE THEN RAISE EXCEPTION 'Vehicle is inactive'; END IF;
    IF v_user_is_active = FALSE THEN RAISE EXCEPTION 'User is inactive'; END IF;
    IF v_user_is_suspended = TRUE THEN RAISE EXCEPTION 'User is suspended'; END IF;
    IF v_vehicle_user_id != p_user_id THEN RAISE EXCEPTION 'Vehicle does not belong to user'; END IF;
    IF v_vehicle_connector_type != v_port_connector_type THEN RAISE EXCEPTION 'Connector mismatch'; END IF;
    IF v_user_banned_until IS NOT NULL AND v_user_banned_until > CURRENT_TIMESTAMP THEN RAISE EXCEPTION 'User is banned'; END IF;

    -- Financial / State Validations
    SELECT COUNT(*) INTO v_active_reservations FROM RESERVATIONS WHERE user_id = p_user_id AND status IN ('Confirmed', 'Active');
    IF v_active_reservations > 0 THEN RAISE EXCEPTION 'User already has an active reservation'; END IF;

    SELECT COUNT(*) INTO v_active_sessions FROM CHARGING_SESSIONS cs JOIN RESERVATIONS r ON cs.reservation_id = r.reservation_id WHERE r.vehicle_id = p_vehicle_id AND cs.end_time IS NULL;
    IF v_active_sessions > 0 THEN RAISE EXCEPTION 'Vehicle already has an active session'; END IF;

    SELECT COUNT(*) INTO v_unpaid_invoices FROM INVOICES WHERE user_id = p_user_id AND is_paid = FALSE;
    IF v_unpaid_invoices > 0 THEN RAISE EXCEPTION 'User has unpaid invoices'; END IF;

    IF v_user_wallet_balance < (1000 + v_station_minimum_fee) THEN RAISE EXCEPTION 'Insufficient wallet balance for pre-auth hold'; END IF;

    -- Waitlist checking
    SELECT COUNT(*) INTO v_waitlist_offer FROM WAITLIST WHERE user_id = p_user_id AND offered_port_id IS NOT NULL;
    IF v_waitlist_offer > 0 THEN RAISE EXCEPTION 'User currently holds an active waitlist offer'; END IF;

    -- Time boundary checking
    IF v_station_shift_end IS NOT NULL THEN
        IF CURRENT_TIMESTAMP < v_station_shift_start OR CURRENT_TIMESTAMP + INTERVAL '30 MINUTE' > v_station_shift_end THEN
            RAISE EXCEPTION 'Station is closed or closing within 30 minutes. Cannot meet minimum charge SLA.';
        END IF;
    END IF;

    -- Cooldown check
    IF EXISTS (
        SELECT 1 FROM RESERVATIONS r JOIN CHARGING_PORTS p ON r.port_id = p.port_id
        WHERE r.user_id = p_user_id AND p.station_id = v_station_id AND r.status = 'Cancelled'
        AND r.status_updated_at > CURRENT_TIMESTAMP - (p_cooldown_minutes || ' minutes')::INTERVAL
    ) THEN
        RAISE EXCEPTION 'User is in cancellation cooldown for this station';
    END IF;

    -- Update state
    UPDATE CHARGING_PORTS SET status = 'Reserved' WHERE port_id = p_port_id;
    -- Tier 3.5: Delete waitlist if exists
    DELETE FROM WAITLIST WHERE user_id = p_user_id;

    -- Tier 4: Reservations
    INSERT INTO RESERVATIONS (user_id, vehicle_id, port_id, status, reserved_tariff)
    VALUES (p_user_id, p_vehicle_id, p_port_id, 'Confirmed', v_station_price_per_kwh)
    RETURNING reservation_id INTO v_new_reservation_id;

    -- wallet_balance is maintained by trg_update_wallet_balance from this ledger row.
    INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (p_user_id, -1000, 'Escrow Hold', v_new_reservation_id);

END;
$$;

CREATE OR REPLACE PROCEDURE sp_ConfirmWaitlist(
    p_user_id UUID,
    p_waitlist_id UUID,
    p_port_id UUID,
    p_grace_period_minutes INT,
    p_cooldown_minutes INT,
    p_ip_address VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id UUID;
    v_station_id UUID;
    v_port_status port_status_enum;
    v_port_is_pending_maintenance BOOLEAN;
    v_port_connector_type VARCHAR;
    v_port_is_active BOOLEAN;
    v_vehicle_user_id UUID;
    v_vehicle_connector_type VARCHAR;
    v_vehicle_is_active BOOLEAN;
    v_user_wallet_balance DECIMAL;
    v_user_banned_until TIMESTAMP;
    v_user_is_active BOOLEAN;
    v_waitlist_offered_port_id UUID;
    v_waitlist_offered_at TIMESTAMP;
    v_waitlist_joined_tariff DECIMAL;
    v_waitlist_joined_minimum_fee DECIMAL;
    v_waitlist_joined_at TIMESTAMP;
    v_station_minimum_fee DECIMAL;
    v_station_price_per_kwh DECIMAL;
    v_station_is_active BOOLEAN;
    v_company_is_active BOOLEAN;
    v_company_is_deprecating BOOLEAN;
    v_station_shift_start TIMESTAMP;
    v_station_shift_end TIMESTAMP;
    v_active_reservations INT;
    v_active_sessions INT;
    v_unpaid_invoices INT;
    v_vehicle_id UUID;
    v_new_reservation_id UUID;
BEGIN
    -- Tier 1: Companies > Stations
    SELECT s.company_id, s.station_id INTO v_company_id, v_station_id
    FROM CHARGING_PORTS p JOIN STATIONS s ON p.station_id = s.station_id WHERE p.port_id = p_port_id;

    SELECT is_active, is_deprecating INTO v_company_is_active, v_company_is_deprecating FROM COMPANIES WHERE company_id = v_company_id FOR SHARE;
    SELECT is_active, minimum_session_fee, price_per_kwh, current_shift_start_utc, current_shift_end_utc
    INTO v_station_is_active, v_station_minimum_fee, v_station_price_per_kwh, v_station_shift_start, v_station_shift_end
    FROM STATIONS WHERE station_id = v_station_id FOR SHARE;

    -- Tier 2: Charging Ports
    SELECT status, connector_type, is_active, is_pending_maintenance INTO v_port_status, v_port_connector_type, v_port_is_active, v_port_is_pending_maintenance
    FROM CHARGING_PORTS WHERE port_id = p_port_id FOR UPDATE;

    -- Get vehicle from waitlist to lock it
    SELECT vehicle_id INTO v_vehicle_id FROM WAITLIST WHERE waitlist_id = p_waitlist_id;

    -- Tier 2.5: Vehicles
    SELECT user_id, connector_type, is_active INTO v_vehicle_user_id, v_vehicle_connector_type, v_vehicle_is_active
    FROM VEHICLES WHERE vehicle_id = v_vehicle_id FOR SHARE;

    -- Tier 3: Users
    SELECT wallet_balance, banned_until, is_active INTO v_user_wallet_balance, v_user_banned_until, v_user_is_active
    FROM USERS WHERE user_id = p_user_id FOR UPDATE;

    -- Tier 3.5: Waitlist
    SELECT offered_port_id, offered_at, joined_tariff, joined_minimum_fee, joined_at
    INTO v_waitlist_offered_port_id, v_waitlist_offered_at, v_waitlist_joined_tariff, v_waitlist_joined_minimum_fee, v_waitlist_joined_at
    FROM WAITLIST WHERE waitlist_id = p_waitlist_id FOR UPDATE;

    -- Validations
    IF v_port_status != 'Pending Waitlist' THEN RAISE EXCEPTION 'Port is not Pending Waitlist'; END IF;
    IF v_port_is_pending_maintenance = TRUE THEN RAISE EXCEPTION 'Port is pending maintenance'; END IF;
    IF v_waitlist_offered_port_id != p_port_id THEN RAISE EXCEPTION 'Waitlist offer IDOR check failed'; END IF;
    IF v_company_is_active = FALSE OR v_company_is_deprecating = TRUE THEN RAISE EXCEPTION 'Company is inactive or deprecating'; END IF;
    IF v_station_is_active = FALSE THEN RAISE EXCEPTION 'Station is inactive'; END IF;
    IF v_port_is_active = FALSE THEN RAISE EXCEPTION 'Port is inactive'; END IF;
    IF v_vehicle_is_active = FALSE THEN RAISE EXCEPTION 'Vehicle is inactive'; END IF;
    IF v_user_is_active = FALSE THEN RAISE EXCEPTION 'User is inactive'; END IF;
    IF v_vehicle_user_id != p_user_id THEN RAISE EXCEPTION 'Vehicle does not belong to user'; END IF;
    IF v_vehicle_connector_type != v_port_connector_type THEN RAISE EXCEPTION 'Connector mismatch'; END IF;
    IF v_user_banned_until IS NOT NULL AND v_user_banned_until > CURRENT_TIMESTAMP THEN RAISE EXCEPTION 'User is banned'; END IF;

    SELECT COUNT(*) INTO v_active_reservations FROM RESERVATIONS WHERE user_id = p_user_id AND status IN ('Confirmed', 'Active');
    IF v_active_reservations > 0 THEN RAISE EXCEPTION 'User already has an active reservation'; END IF;

    SELECT COUNT(*) INTO v_active_sessions FROM CHARGING_SESSIONS cs JOIN RESERVATIONS r ON cs.reservation_id = r.reservation_id WHERE r.vehicle_id = v_vehicle_id AND cs.end_time IS NULL;
    IF v_active_sessions > 0 THEN RAISE EXCEPTION 'Vehicle already has an active session'; END IF;

    SELECT COUNT(*) INTO v_unpaid_invoices FROM INVOICES WHERE user_id = p_user_id AND is_paid = FALSE;
    IF v_unpaid_invoices > 0 THEN RAISE EXCEPTION 'User has unpaid invoices'; END IF;

    IF v_user_wallet_balance < (1000 + v_waitlist_joined_minimum_fee) THEN RAISE EXCEPTION 'Insufficient wallet balance based on waitlist joined minimum fee'; END IF;
    IF CURRENT_TIMESTAMP >= v_waitlist_offered_at + INTERVAL '90 SECOND' THEN RAISE EXCEPTION 'Waitlist offer expired'; END IF;

    IF v_station_shift_end IS NOT NULL THEN
        IF CURRENT_TIMESTAMP >= v_station_shift_start AND CURRENT_TIMESTAMP + INTERVAL '30 MINUTE' > v_station_shift_end THEN
            RAISE EXCEPTION 'Station is closing within 30 minutes.';
        END IF;
    END IF;

    IF EXISTS (
        SELECT 1 FROM RESERVATIONS r JOIN CHARGING_PORTS p ON r.port_id = p.port_id
        WHERE r.user_id = p_user_id AND p.station_id = v_station_id AND r.status = 'Cancelled'
        AND r.status_updated_at > CURRENT_TIMESTAMP - (p_cooldown_minutes || ' minutes')::INTERVAL
    ) THEN
        RAISE EXCEPTION 'User is in cancellation cooldown for this station';
    END IF;

    -- Update state
    UPDATE CHARGING_PORTS SET status = 'Reserved' WHERE port_id = p_port_id;
    
    -- Tier 4: Reservations
    INSERT INTO RESERVATIONS (user_id, vehicle_id, port_id, status, waitlist_joined_at, reserved_tariff)
    VALUES (p_user_id, v_vehicle_id, p_port_id, 'Confirmed', v_waitlist_joined_at, LEAST(v_waitlist_joined_tariff, v_station_price_per_kwh))
    RETURNING reservation_id INTO v_new_reservation_id;

    -- Escrow update: wallet_balance is maintained by trg_update_wallet_balance from this ledger row.
    INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (p_user_id, -1000, 'Escrow Hold', v_new_reservation_id);

    DELETE FROM WAITLIST WHERE waitlist_id = p_waitlist_id;

END;
$$;


CREATE OR REPLACE PROCEDURE sp_JoinWaitlist(
    p_user_id UUID,
    p_station_id UUID,
    p_vehicle_id UUID,
    p_closing_buffer_minutes INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id UUID;
    v_company_is_active BOOLEAN;
    v_company_is_deprecating BOOLEAN;
    v_station_is_active BOOLEAN;
    v_station_minimum_fee DECIMAL;
    v_station_price_per_kwh DECIMAL;
    v_station_shift_end TIMESTAMP;
    v_vehicle_user_id UUID;
    v_vehicle_connector_type VARCHAR;
    v_vehicle_is_active BOOLEAN;
    v_user_wallet_balance DECIMAL;
    v_user_banned_until TIMESTAMP;
    v_user_is_active BOOLEAN;
    v_existing_waitlist INT;
    v_operational_ports INT;
    v_available_unwarned_ports INT;
    v_new_waitlist_id UUID;
BEGIN
    -- Tier 1: Companies > Stations
    SELECT company_id INTO v_company_id FROM STATIONS WHERE station_id = p_station_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Station not found'; END IF;

    SELECT is_active, is_deprecating INTO v_company_is_active, v_company_is_deprecating
    FROM COMPANIES WHERE company_id = v_company_id FOR SHARE;

    SELECT is_active, minimum_session_fee, price_per_kwh, current_shift_end_utc
    INTO v_station_is_active, v_station_minimum_fee, v_station_price_per_kwh, v_station_shift_end
    FROM STATIONS WHERE station_id = p_station_id FOR SHARE;

    -- Optimistic (unlocked) read of the connector type, only to scope the port lock below.
    -- The global hierarchy is CHARGING_PORTS (Tier 2) -> VEHICLES (Tier 2.5); locking the
    -- vehicle first would invert that order and risk deadlocking against sp_ConfirmWaitlist
    -- and cancel_reservation, which both lock ports before vehicles.
    SELECT connector_type INTO v_vehicle_connector_type FROM VEHICLES WHERE vehicle_id = p_vehicle_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'Vehicle not found'; END IF;

    -- Tier 2: Charging Ports (lock every compatible port at this station in a stable order)
    PERFORM 1 FROM CHARGING_PORTS
    WHERE station_id = p_station_id AND connector_type = v_vehicle_connector_type
    ORDER BY port_id FOR SHARE;

    -- Tier 2.5: Vehicles (re-validated now, under lock, after the port lock is held)
    SELECT user_id, connector_type, is_active INTO v_vehicle_user_id, v_vehicle_connector_type, v_vehicle_is_active
    FROM VEHICLES WHERE vehicle_id = p_vehicle_id FOR SHARE;

    -- Tier 3: Users
    SELECT wallet_balance, banned_until, is_active INTO v_user_wallet_balance, v_user_banned_until, v_user_is_active
    FROM USERS WHERE user_id = p_user_id FOR UPDATE;

    -- Validations
    IF v_company_is_active = FALSE OR v_company_is_deprecating = TRUE THEN RAISE EXCEPTION 'Company is inactive or deprecating'; END IF;
    IF v_station_is_active = FALSE THEN RAISE EXCEPTION 'Station is inactive'; END IF;
    IF v_vehicle_is_active = FALSE THEN RAISE EXCEPTION 'Vehicle is inactive'; END IF;
    IF v_vehicle_user_id != p_user_id THEN RAISE EXCEPTION 'Vehicle does not belong to user'; END IF;
    IF v_user_is_active = FALSE THEN RAISE EXCEPTION 'User is inactive'; END IF;
    IF v_user_banned_until IS NOT NULL AND v_user_banned_until > CURRENT_TIMESTAMP THEN RAISE EXCEPTION 'User is banned'; END IF;

    SELECT COUNT(*) INTO v_existing_waitlist FROM WAITLIST WHERE user_id = p_user_id;
    IF v_existing_waitlist > 0 THEN RAISE EXCEPTION 'User already has an active waitlist entry'; END IF;

    IF v_user_wallet_balance < (1000 + v_station_minimum_fee) THEN RAISE EXCEPTION 'Insufficient wallet balance for pre-auth hold'; END IF;

    SELECT COUNT(*) INTO v_operational_ports FROM CHARGING_PORTS
    WHERE station_id = p_station_id AND connector_type = v_vehicle_connector_type
      AND is_active = TRUE AND status NOT IN ('Offline', 'Maintenance');
    IF v_operational_ports = 0 THEN RAISE EXCEPTION 'No operational ports for this connector type at this station'; END IF;

    SELECT COUNT(*) INTO v_available_unwarned_ports FROM CHARGING_PORTS
    WHERE station_id = p_station_id AND connector_type = v_vehicle_connector_type
      AND is_active = TRUE AND status = 'Available' AND has_health_warning = FALSE AND has_blocked_warning = FALSE;
    IF v_available_unwarned_ports > 0 THEN RAISE EXCEPTION 'An available port exists; reserve it directly instead of joining the waitlist'; END IF;

    IF v_station_shift_end IS NOT NULL THEN
        IF CURRENT_TIMESTAMP + (p_closing_buffer_minutes || ' minutes')::INTERVAL > v_station_shift_end THEN
            RAISE EXCEPTION 'Station is closing too soon to join the waitlist';
        END IF;
    END IF;

    INSERT INTO WAITLIST (user_id, station_id, vehicle_id, joined_tariff, joined_minimum_fee)
    VALUES (p_user_id, p_station_id, p_vehicle_id, v_station_price_per_kwh, v_station_minimum_fee)
    RETURNING waitlist_id INTO v_new_waitlist_id;

END;
$$;

CREATE OR REPLACE PROCEDURE sp_StartSession(
    p_user_id UUID,
    p_reservation_id UUID,
    p_initial_battery_percentage DECIMAL,
    p_target_battery_percentage DECIMAL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_station_id UUID;
    v_port_id UUID;
    v_vehicle_id UUID;
    v_res_status reservation_status_enum;
    v_res_user_id UUID;
    v_port_status port_status_enum;
    v_port_is_pending_maintenance BOOLEAN;
    v_user_is_suspended BOOLEAN;
    v_unpaid_invoices INT;
    v_user_wallet_balance DECIMAL;
    v_station_minimum_fee DECIMAL;
    v_station_price_per_kwh DECIMAL;
    v_station_shift_end TIMESTAMP;
    v_vehicle_battery_capacity DECIMAL;
    v_next_maintenance TIMESTAMP;
    v_available_time_seconds INT;
    v_clamped_target_battery DECIMAL;
    v_secondary_cost DECIMAL;
BEGIN
    -- Resolve IDs safely without locks first to figure out hierarchy
    SELECT port_id, vehicle_id INTO v_port_id, v_vehicle_id FROM RESERVATIONS WHERE reservation_id = p_reservation_id;
    SELECT station_id INTO v_station_id FROM CHARGING_PORTS WHERE port_id = v_port_id;

    -- Tier 1: Stations
    SELECT minimum_session_fee, price_per_kwh, current_shift_end_utc
    INTO v_station_minimum_fee, v_station_price_per_kwh, v_station_shift_end
    FROM STATIONS WHERE station_id = v_station_id FOR SHARE;

    -- Tier 2: Ports
    SELECT status, is_pending_maintenance INTO v_port_status, v_port_is_pending_maintenance FROM CHARGING_PORTS WHERE port_id = v_port_id FOR UPDATE;

    -- Tier 2.5: Vehicles
    SELECT battery_capacity INTO v_vehicle_battery_capacity FROM VEHICLES WHERE vehicle_id = v_vehicle_id FOR SHARE;

    -- Tier 3: Users
    SELECT is_suspended, wallet_balance INTO v_user_is_suspended, v_user_wallet_balance FROM USERS WHERE user_id = p_user_id FOR UPDATE;

    -- Tier 4: Reservations
    SELECT status, user_id INTO v_res_status, v_res_user_id FROM RESERVATIONS WHERE reservation_id = p_reservation_id FOR UPDATE;

    -- Validations
    IF v_res_user_id != p_user_id THEN RAISE EXCEPTION 'Reservation IDOR check failed'; END IF;
    IF v_res_status != 'Confirmed' THEN RAISE EXCEPTION 'Reservation is not Confirmed'; END IF;
    IF v_user_is_suspended = TRUE THEN RAISE EXCEPTION 'User is suspended'; END IF;
    IF v_port_status != 'Reserved' THEN RAISE EXCEPTION 'Port is not Reserved'; END IF;
    -- DD-13: pending-maintenance validation is mandatory at session start
    IF v_port_is_pending_maintenance = TRUE THEN RAISE EXCEPTION 'Port is pending maintenance'; END IF;

    SELECT COUNT(*) INTO v_unpaid_invoices FROM INVOICES WHERE user_id = p_user_id AND is_paid = FALSE;
    IF v_unpaid_invoices > 0 THEN RAISE EXCEPTION 'User has unpaid invoices'; END IF;

    -- Calculate max available time
    v_available_time_seconds := 86400 * 365; -- Defaults to 1 year
    IF v_station_shift_end IS NOT NULL THEN
        v_available_time_seconds := LEAST(v_available_time_seconds, EXTRACT(EPOCH FROM (v_station_shift_end - CURRENT_TIMESTAMP))::INT);
    END IF;

    SELECT MIN(start_time) INTO v_next_maintenance FROM MAINTENANCE_SCHEDULES WHERE port_id = v_port_id AND status = 'Scheduled' AND start_time > CURRENT_TIMESTAMP;
    IF v_next_maintenance IS NOT NULL THEN
        v_available_time_seconds := LEAST(v_available_time_seconds, EXTRACT(EPOCH FROM (v_next_maintenance - CURRENT_TIMESTAMP))::INT);
    END IF;

    -- If available time < 15 mins and station closes in > 30 mins, fail. (If station closing within 30, it allows walkins).
    IF v_available_time_seconds < 900 THEN
        IF v_station_shift_end IS NULL OR EXTRACT(EPOCH FROM (v_station_shift_end - CURRENT_TIMESTAMP)) > 1800 THEN
             RAISE EXCEPTION 'Insufficient time available (less than 15 mins) before maintenance/closing';
        END IF;
    END IF;

    -- Calculate clamping and costs (simplified clamped calculation logic per requirements)
    v_clamped_target_battery := p_target_battery_percentage;
    -- Note: Real system might calculate exactly how many kWh can be delivered in v_available_time_seconds.
    -- For now we just use the target to calculate cost:
    
    v_secondary_cost := GREATEST(v_station_minimum_fee, ((v_clamped_target_battery - p_initial_battery_percentage) / 100.0 * v_vehicle_battery_capacity * v_station_price_per_kwh));

    -- Escrow refund temporarily for calculation
    v_user_wallet_balance := v_user_wallet_balance + 1000;

    IF v_user_wallet_balance < (v_secondary_cost + 1000) THEN
        RAISE EXCEPTION '402 Payment Required. Insufficient funds for secondary energy pre-authorization.';
    END IF;

    -- Escrow deduct: release the original 1000 hold, take the energy pre-auth as a
    -- real payment, then re-hold 1000 for idle-fee risk. wallet_balance is maintained
    -- by trg_update_wallet_balance as SUM(WALLET_TRANSACTIONS) - the net effect of
    -- these three ledger rows is a single -v_secondary_cost (the two 1000s cancel
    -- out), but each leg is recorded separately so it stays independently auditable.
    INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (p_user_id, 1000, 'Escrow Release', p_reservation_id);
    INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (p_user_id, -v_secondary_cost, 'Session Payment', p_reservation_id);
    INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (p_user_id, -1000, 'Escrow Hold', p_reservation_id);
    UPDATE RESERVATIONS SET status = 'Active' WHERE reservation_id = p_reservation_id;
    -- FR-16: a successful session instantly clears any health warning on the port
    UPDATE CHARGING_PORTS SET status = 'Charging', has_health_warning = FALSE WHERE port_id = v_port_id;

    INSERT INTO CHARGING_SESSIONS (reservation_id, initial_battery_percentage, target_battery_percentage, applied_tariff)
    VALUES (p_reservation_id, p_initial_battery_percentage, v_clamped_target_battery, v_station_price_per_kwh);

END;
$$;
