// Electra mocks device GPS (see PRD "Out-of-Scope: GPS navigation and GIS integration").
// Every driver-side location check — search radius, waitlist proximity — resolves
// to this fixed Bengaluru coordinate so behavior stays consistent across the app.
export const MOCK_USER_LAT = 12.9716;
export const MOCK_USER_LNG = 77.5946;
