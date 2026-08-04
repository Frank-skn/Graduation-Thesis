/**
 * Simple module-level cache (lives outside the component lifecycle).
 * Used for APIs that change little within a session (data overview,
 * algorithm/cost parameters...) to avoid refetching every time the user
 * leaves and returns to a page — React Router unmounts the component so
 * component state is lost, but the cache here is not.
 *
 * The cache is naturally cleared on page reload (F5) — this is the
 * desired behavior; no need for a complex expiration mechanism for a
 * single working session.
 */
const cache = new Map();

export function getCached(key) {
  return cache.has(key) ? cache.get(key) : undefined;
}

export function setCached(key, value) {
  cache.set(key, value);
}

export function invalidateCache(key) {
  if (key) {
    cache.delete(key);
  } else {
    cache.clear();
  }
}
