// Device GPS integration with fallback to Bengaluru coordinates
export const MOCK_USER_LAT = 12.9716;
export const MOCK_USER_LNG = 77.5946;

export async function getUserLocation(): Promise<{ lat: number; lng: number }> {
  if (typeof navigator !== 'undefined' && 'geolocation' in navigator) {
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000, enableHighAccuracy: true });
      });
      return {
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      };
    } catch {
      // Fallback to default mock coords if permission denied or timeout
    }
  }
  return { lat: MOCK_USER_LAT, lng: MOCK_USER_LNG };
}
