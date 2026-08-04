import { useState, useEffect, useCallback } from 'react';
import { getCached, setCached } from './apiCache';

/**
 * Reusable hook for async API data fetching.
 * @param {Function} fetchFn - async function returning data
 * @param {Array} deps - dependency array (re-fetches when changed)
 * @param {Object} options - { immediate: bool, cacheKey: string }
 *   cacheKey: if provided, the result is stored in a module-level cache
 *   (lives outside the component lifecycle). On the next mount (e.g.
 *   returning to the page), the cached data is shown IMMEDIATELY (no
 *   loading state), then the API is still called in the background to
 *   sync — suited for data that changes little within a session
 *   (overview, parameters...).
 */
export function useApi(fetchFn, deps = [], options = {}) {
  const { immediate = true, cacheKey = null } = options;
  const cached = cacheKey ? getCached(cacheKey) : undefined;
  const [data, setData] = useState(cached ?? null);
  const [loading, setLoading] = useState(immediate && cached === undefined);
  const [error, setError] = useState(null);

  const execute = useCallback(async (...args) => {
    // Cache already present → show immediately, no loading flicker; still fetch in the background to sync.
    setLoading(cacheKey ? getCached(cacheKey) === undefined : true);
    setError(null);
    try {
      const result = await fetchFn(...args);
      setData(result);
      if (cacheKey) setCached(cacheKey, result);
      return result;
    } catch (err) {
      setError(err.message || 'An error occurred');
      return null;
    } finally {
      setLoading(false);
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (immediate) {
      execute();
    }
  }, [execute, immediate]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, execute, reset };
}

/**
 * Hook for mutation-style API calls (POST/PUT/DELETE).
 * Does not auto-fetch on mount.
 * @param {Function} mutationFn - async function
 */
export function useMutation(mutationFn) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const mutate = useCallback(async (...args) => {
    setLoading(true);
    setError(null);
    try {
      const result = await mutationFn(...args);
      setData(result);
      return result;
    } catch (err) {
      setError(err.message || 'An error occurred');
      return null;
    } finally {
      setLoading(false);
    }
  }, [mutationFn]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, mutate, reset };
}

export default useApi;
