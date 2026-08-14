# Phase 5 Project Status and Usage

## 1. Project Overview
Electra is a Multi-Operator EV Charging Management System designed to provide a centralized, full-stack application for EV charging. It enables users to search, reserve, and manage charging sessions across multiple independent network operators. The system currently encompasses robust database procedures, a FastAPI backend, and a React/Vite frontend.

## 2. Architecture
- **Database:** PostgreSQL with PostGIS for spatial queries. Uses strict PL/pgSQL stored procedures (`sp_CreateReservation`, `sp_StartSession`, etc.) to enforce ACID compliance and hierarchical row-level locking.
- **Backend:** Python FastAPI using SQLAlchemy for ORM. Structured with routers, controllers, services, and Pydantic schemas. Authentication relies on JWTs with Redis for blocklisting.
- **Frontend:** React + TypeScript + Vite using Tailwind CSS v4. Incorporates Leaflet for maps. Uses Axios for API communication.

## 3. Phase 1–5 Implementation Summary
- **Phase 1 (Database Architecture):** PASS. Schemas, triggers, and procedures (`01_schema.sql`, `02_procedures.sql`) are robust and correctly enforce locking tiers and soft-delete restrictions.
- **Phase 2 (Backend Foundations & Auth):** PASS. FastAPI initialized, JWT authentication and RBAC roles implemented. Frontend Login/Register pages built.
- **Phase 3 (Driver Core):** PASS. Dashboard, Vehicle management, User profiles implemented.
- **Phase 3.5 (Internal Wallet Ledger):** PASS. Wallet schema, transactions, triggers, and mock API endpoints exist.
- **Phase 4 (Operator & Admin):** PASS. Company and Station/Port CRUD implemented with admin/operator dashboards.
- **Phase 5 (Search & Core Reservations):** PARTIAL. Search is implemented using PostGIS `ST_DWithin`. Core reservation engine is backed by `sp_CreateReservation`. However, automatic port recommendation fails to exclude blocked/faulty chargers, and reservation expiry doesn't trigger waitlist promotion.

## 4. Current Feature Inventory
**Verified Working:**
- User Authentication (Login, Register)
- Station Search & Map Rendering (Leaflet)
- Favorites and Recent Stations caching
- Database Schema and Stored Procedures for reservations

**Partially Working / Implemented but Unverified:**
- Reservation Creation (Endpoint exists and uses DB procedure, but edge cases around port recommendation are flawed).
- Reservation Cancellation (Endpoint exists, calculates refunds vs. penalties based on user trust and timeframe, but missing integration testing).

**Broken or Missing in Phase 5:**
- Automatic waitlist promotion on reservation expiry (Waitlist is Phase 6, but PRD dictates immediate promotion on expiry).
- Automatic port recommendation ignores `has_health_warning` and `has_blocked_warning`.

## 5. Setup Guide
1. Clone the repository.
2. Run PostgreSQL (with PostGIS) and Redis via Docker (use `docker-compose up -d`).
3. Install backend dependencies: `cd backend && python -m venv .venv && .\.venv\Scripts\activate && pip install -r requirements.txt`.
4. Install frontend dependencies: `cd frontend && npm install`.

## 6. Configuration
Create a `.env` file in the `backend` directory:
```
DATABASE_URL=postgresql://user:password@localhost:5432/electra
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your_secret_key
JWT_ALGORITHM=HS256
```

## 7. Running the Project
**Database Setup:**
Execute `database/01_schema.sql`, `02_procedures.sql`, and `03_seed_data.sql` sequentially in your Postgres instance.

**Backend Startup:**
```bash
cd backend
.\.venv\Scripts\activate
uvicorn app.main:app --reload
```

**Frontend Startup:**
```bash
cd frontend
npm run dev
```

## 8. Using the Implemented Features
- **Search:** Access the Driver Dashboard. The map will load nearby stations within a given radius using the `POST /search/stations` endpoint.
- **Reservations:** Select a station on the map, click "View Details", and initiate a reservation. Ensure your wallet has at least INR 1000.
- **Favorites:** Click the heart icon on a station to save it. It will appear in the Favorites list on the dashboard.

## 9. Testing Guide
**Backend Testing:**
```bash
cd backend
.\.venv\Scripts\activate
pytest tests/
```

**Frontend Linter:**
```bash
cd frontend
npm run lint
```

## 10. Expected Results
The backend server should start on port 8000 and the frontend on port 5173. Searching on the frontend should display markers on the map corresponding to the seed data in Postgres.

## 11. Known Issues
- `AUD-001`: Auto-recommendation ignores charger health warnings.
- `AUD-002`: Very limited backend test coverage.
- `AUD-003`: `clean_expired_reservations` does not trigger waitlist promotion on timeout.

## 12. Limitations
- Waitlist and charging session simulations (Phases 6 and 7) are not yet integrated into the frontend flow.
- Mock payment endpoint for wallet top-up requires manual testing via Swagger UI.

## 13. Troubleshooting
- **Leaflet Marker Issues:** The default icons are correctly overridden in `SearchStations.tsx`, but ensure internet connectivity for CDN images.
- **PostGIS Errors:** Ensure the Postgres database has the `postgis` extension created (`CREATE EXTENSION postgis;`).

## 14. Phase 5 Baseline
As of this audit, Phase 5 is structurally complete but functionally flawed on edge cases. The application successfully connects driver accounts, vehicle selection, wallet balances, and PostGIS searches to the `sp_CreateReservation` engine. Remediation of `AUD-001` and `AUD-003` is required before progressing to Phase 6 (Waitlists).
