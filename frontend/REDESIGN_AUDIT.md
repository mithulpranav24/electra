# Electra frontend redesign audit

This inventory is the behavioral contract for the redesign. It records the product as found on 2026-08-15 before replacement work began.

## Product and audiences

Electra is a multi-operator EV charging product with three authenticated roles:

- **Driver:** find compatible chargers, inspect stations, save favorites, reserve a port, manage vehicles, fund a wallet, and manage an account.
- **Operator:** manage the first assigned company's stations and charging ports, including their map locations.
- **Admin:** create companies, assign operator accounts by user UUID, and inspect company status.

The backend is FastAPI with JWT authentication and unified `{ success, data }` responses. The frontend is React 19, React Router 7, TypeScript, Vite, Tailwind CSS 4, Axios, Leaflet, and lucide-react.

## Routes and access behavior

| Route | Access | Existing capability that must survive |
| --- | --- | --- |
| `/` | Public redirect | Wait for auth initialization, then route to the role's dashboard or login. |
| `/login` | Public | Form-url-encoded email/password login, error detail handling, role-aware redirect after user hydration. |
| `/register` | Public | Email/password registration, matching-password validation, backend validation details, redirect to login. |
| `/driver/dashboard` | Driver | Dashboard metrics, recent activity, station and wallet quick actions. |
| `/driver/search` | Driver | Search around the fixed Bengaluru coordinates; fast-charging and connector filters; map markers; recents; favorites. |
| `/driver/station/:id` | Driver | Load station and vehicles; favorite toggle; reserve an available port using default/first vehicle; escrow disclosure. |
| `/driver/vehicles` | Driver | List, loading and empty states; create, edit, soft-delete, optimistic default selection with refresh rollback. |
| `/driver/sessions` | Driver | Active/history empty states. |
| `/driver/wallet` | Driver | Balance, top-up, payment methods, transactions, and global user-balance refresh. |
| `/driver/profile` | Driver | Update name/phone; immutable email; account deletion confirmation and logout. |
| `/operator/dashboard` | Operator | Resolve first company membership; list stations/ports; create and delete stations/ports; click-to-place map marker. |
| `/admin/dashboard` | Admin | List/create companies and assign operator membership by user UUID. |
| Unknown paths | Role-aware | Redirect authenticated users to their permitted home and others to login. |

Role protection is exact: Driver, Operator, and Admin routes redirect a signed-in user to the dashboard for their actual role. A `401` clears the persisted token and broadcasts `auth-unauthorized`.

## Data and integration contract

- API base: `http://localhost:8000/api/v1`.
- Auth token persistence key: `localStorage.token`.
- Every authenticated request sends `Authorization: Bearer <token>`.
- The Axios response interceptor unwraps successful unified responses without altering error responses.
- Vehicle list requests carry a timestamp cache buster. Vehicle IDs can be present as `vehicle_id` or legacy `id`; mutations must tolerate both.
- Login remains `application/x-www-form-urlencoded` with the email sent as `username`.
- Registration remains JSON and must satisfy the backend's eight-character, non-common-password rules.
- Station search remains `POST /search/stations` with `lat`, `lng`, `radius_km <= 500`, nullable `connector_type`, and nullable `min_power_kw`.
- Viewing station details records a recent station on the backend.
- Reservations remain `POST /reservations` with `port_id` and `vehicle_id`. The UI must disclose the INR 1,000 escrow and 15-minute arrival window.
- Wallet top-up remains `POST /wallet/topup` and must refresh balance, transactions, and `AuthContext`.
- Operator station coordinates remain `lat`/`lng`; currency values remain numeric; port creation remains attached to a selected station.
- Deletes are backend soft deletes/deprecation operations even if the existing UI says “delete.”

## Backend-supported operations already represented in the frontend service layer

These calls were present even where the old screen did not surface them clearly. The redesign may expose them without changing their contracts:

- Update a company and list its operator memberships.
- Update a station.
- Update a charging port, including operational status and warning flags.
- Fetch active reservations and cancel a confirmed reservation (backend route present, previously not surfaced by the UI).
- Update the signed-in user's password (backend route present, previously not surfaced by the UI).

They will only be added where they complete an existing workflow; no backend contract will be rewritten.

## Required state coverage

Each server-backed view must distinguish initial loading, background refresh/submission, success, empty, failure, and disabled states. Search must distinguish “no stations match” from “not searched.” Destructive actions require contextual confirmation. Dialogs require labelled structure, Escape handling, initial focus, focus containment, and focus restoration. Long identifiers, names, QR codes, timestamps, and data tables must wrap or scroll intentionally.

Mobile keeps all primary functionality. Desktop navigation becomes a task-oriented rail; narrow layouts become a compact header and bottom navigation. Dense tables become labelled record rows/cards rather than relying on horizontal compression.

## Baseline defects discovered before redesign

The pre-redesign production build failed with six TypeScript issues: one possibly undefined vehicle ID and five unused imports. Lint completed with 12 warnings, including the same unused values, unused catches, a missing search effect dependency, and a Fast Refresh warning. Backend tests could not start because `pytest` is absent from the selected Python runtime. These are baseline findings, not redesign regressions, and will be resolved or rechecked during migration.

Other behavior risks found in the old UI:

- Several visible controls were inert or misleading (`Top up` in the side rail and dashboard `View All`).
- Admin/operator “Back to Main” links pointed to a driver-only route and were immediately redirected by role protection.
- Loading and request failure states were absent on the admin/operator dashboards.
- Native alerts/confirms were the only feedback for many important operations.
- Dialogs lacked focus management, Escape behavior, accessible naming, and reliable mobile overflow.
- Search rendered a large map before a result list, making station comparison difficult, and had no explicit no-results state.
- The “Fast Charging Only (>22kW)” label sent `min_power_kw: 50`, while backend charger-type naming and current operator options are inconsistent. The request value will be preserved to avoid contract drift, while the copy will accurately state 50 kW+.
- Profile updates forced a full-page reload despite `AuthContext.fetchUser` already being exposed.
- The station reservation path silently selected the default/first vehicle and provided no way to change it.
- The sessions page was static even though the backend exposes active reservations and cancellation.
- Operator creation used dollar labels while the rest of the product and reservation logic use INR.
- Leaflet marker assets used two different strategies, including CDN-only icons on driver search.

## New information architecture

### Driver

1. **Home:** next action first; active reservation/session status; wallet and vehicle readiness; recent activity.
2. **Find charging:** result list and map as equal views; filters, recents, and favorites support the search rather than sit below it.
3. **Activity:** active reservations first, then charging-session history empty state until session APIs exist.
4. **Vehicles:** fleet readiness and default vehicle management.
5. **Wallet:** balance/top-up first, transactions second, payment methods as supporting information.
6. **Account:** personal details and destructive account action.

### Operator

One operations workspace prioritizes station health and port availability. Creation and editing happen in focused dialogs; the station list remains visible so operators do not lose context.

### Admin

One organization workspace prioritizes company status, operator assignment, and membership visibility. Forms use contextual company selection and return inline feedback.

## Visual system plan

The interface takes cues from charging hardware and wayfinding rather than generic dashboard decoration.

- **Palette:** Night Grid `#13231f`, Porcelain `#f5f7f4`, Paper `#ffffff`, Charge Teal `#087f6d`, Current Amber `#f0b429`, Signal Red `#c2413a`, and Steel `#60706a`.
- **Type:** a compact geometric display stack for headings, a highly legible UI stack for body copy, and a mono utility stack for prices, coordinates, plates, QR codes, and UUIDs.
- **Layout:** a stable left navigation rail at wide sizes, content-first central canvas, and a bottom task bar on phones. Cards are reserved for bounded records and actions rather than wrapping every section.
- **Signature:** a vertical “charge line” in navigation and status surfaces. It encodes the user's progress from readiness to finding, reserving, and charging, so the visual device carries product meaning.

Self-critique: an all-dark, neon-green EV dashboard would be a predictable category treatment and weaker for long administrative use. The revised direction uses a light operational canvas, restrained dark navigation, and amber/teal only where state and action need attention.

## Regression checklist

- [x] Auth initialization, persisted token, logout, 401 handling, and all role redirects.
- [x] Registration validation and login payload format.
- [x] Driver dashboard data and every quick action.
- [x] Search payload, filters, map, result comparison, recents, favorites, and empty/error states.
- [x] Station load, favorite toggle, vehicle selection, reservation payload, escrow disclosure, and missing-vehicle handling.
- [x] Active reservation display and cancellation.
- [x] Vehicle create/edit/delete/default, ID fallback, validation, rollback, and refresh.
- [x] Wallet parallel load, top-up validation, all refreshes, transaction signs, and payment-method empty state.
- [x] Profile update without stale global data and account deletion.
- [x] Operator membership resolution, station/port list, map placement, create/edit/delete, warnings, and errors.
- [x] Admin companies, creation, membership assignment/list, update flow, and errors.
- [x] Keyboard navigation, dialog behavior, visible focus, reduced motion, and touch targets.
- [x] Purposeful layouts at phone, tablet, laptop, and wide desktop widths.
- [x] Lint, typecheck/production build, focused frontend tests, dependency audit, and exact-viewport browser checks.

## Final verification record

- Frontend lint completes with no findings.
- Production TypeScript and Vite build succeeds with route-level code splitting and no bundle-size warning.
- Eight focused regression tests cover formatting edge cases, reservation eligibility/submission, login payload behavior, and authentication errors.
- npm reports zero known vulnerabilities after the transitive `nanoid` patch update.
- Live browser rendering was measured at 320 px, 390 px, and 1440 px. In each case the document width matched the viewport width. Login API failures and registration validation failures were exercised and remained readable at phone width.
- The existing backend reservation suite ran with its missing GeoAlchemy dependency isolated to a temporary workspace-only folder: two tests passed and the database-seeded case skipped because the test database is unavailable. No backend code, global Python package, or API contract was changed.
