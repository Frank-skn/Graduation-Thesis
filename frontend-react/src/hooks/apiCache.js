/**
 * Simple module-level cache (lives outside the component lifecycle).
 * Used for APIs that rarely change within a single session (data overview,
 * algorithm/cost parameters...) to avoid re-calling the API every time the
 * user leaves and comes back to a page — React Router unmounts the
 * component, so component state is lost, but this cache is not.
 *
 * The cache clears itself on page reload (F5) — this is the intended
 * behavior; no need for a complex expiration mechanism for a single session.
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
