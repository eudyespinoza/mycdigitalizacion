const EARTH_RADIUS_METERS = 6_371_000;

export function distanceMeters(aLat: number, aLon: number, bLat: number, bLon: number) {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const dLat = toRadians(bLat - aLat);
  const dLon = toRadians(bLon - aLon);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(aLat)) * Math.cos(toRadians(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(h));
}

export function requiresReverseLookup(
  originalLat: number,
  originalLon: number,
  movedLat: number,
  movedLon: number,
) {
  return distanceMeters(originalLat, originalLon, movedLat, movedLon) > 150;
}
