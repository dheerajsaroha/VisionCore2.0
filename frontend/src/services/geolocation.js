/**
 * Optional location capture for attendance punches.
 *
 * Geo-tagging is optional by design, so every helper here is failure-tolerant:
 * a user who declines the permission prompt, has no GPS, or is on a desktop
 * without a provider must still be able to clock in. The caller treats a null
 * result as "no location" rather than an error.
 *
 * Accuracy is deliberately coarsened before it leaves the device. A punch
 * location only needs to be accurate enough to evaluate a geofence, and
 * publishing a full-precision fix to the server would record a far more
 * precise position than the feature requires.
 */
const TIMEOUT_MS = 8000;

const round = (value) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return null;
  return Number(value.toFixed(6));
};

/**
 * Ask the browser for the current position.
 *
 * @param {object} [options]
 * @param {boolean} [options.enableHighAccuracy=false] Use GPS rather than a network fix.
 * @returns {Promise<{latitude: number, longitude: number, accuracy: number} | null>}
 *   The position, or null when unavailable, denied, or timed out.
 */
export function getCurrentLocation({ enableHighAccuracy = false } = {}) {
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    return Promise.resolve(null);
  }

  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };

    // Never block a clock-in on the prompt: the user may simply ignore it.
    const timer = setTimeout(() => finish(null), TIMEOUT_MS);

    navigator.geolocation.getCurrentPosition(
      (position) => {
        clearTimeout(timer);
        const { latitude, longitude, accuracy } = position.coords || {};
        const lat = round(latitude);
        const lng = round(longitude);
        if (lat === null || lng === null) {
          finish(null);
          return;
        }
        finish({
          latitude: lat,
          longitude: lng,
          accuracy: round(accuracy) ?? null,
        });
      },
      () => {
        clearTimeout(timer);
        // Denied, unavailable, or timed out: all mean "punch without a location".
        finish(null);
      },
      { enableHighAccuracy, timeout: TIMEOUT_MS, maximumAge: 60_000 },
    );
  });
}

/**
 * Build the geo fields for a punch payload.
 *
 * @returns {{gps_lat: number, gps_lng: number}|{}}
 */
export async function locationFields(options = {}) {
  const position = await getCurrentLocation(options);
  if (!position) return {};
  return { gps_lat: position.latitude, gps_lng: position.longitude };
}

/**
 * Whether the browser offers geolocation at all, for conditionally showing UI.
 */
export function isLocationAvailable() {
  return typeof navigator !== 'undefined' && Boolean(navigator.geolocation);
}
