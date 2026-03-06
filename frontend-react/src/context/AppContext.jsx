import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import optimizationService from '../services/optimizationService';

const AppContext = createContext(null);

// ── Helpers: persist run/scenario across page refresh ──────────────
const LS_RUN = 'smi_active_run_id';
const LS_SCENARIO = 'smi_active_scenario_id';
function lsGet(key) {
  try { const v = localStorage.getItem(key); return v ? Number(v) : null; } catch { return null; }
}
function lsSet(key, val) {
  try { if (val != null) localStorage.setItem(key, String(val)); else localStorage.removeItem(key); } catch {}
}

export function AppProvider({ children }) {
  // Initialize from localStorage so page-refresh doesn't lose context
  const [activeScenarioId, _setActiveScenarioId] = useState(() => lsGet(LS_SCENARIO));
  const [activeRunId, _setActiveRunId] = useState(() => lsGet(LS_RUN));
  const [compareRunId, setCompareRunId] = useState(null);
  const [notifications, setNotifications] = useState([]);

  const setActiveScenarioId = useCallback((id) => {
    _setActiveScenarioId(id);
    lsSet(LS_SCENARIO, id);
  }, []);

  const setActiveRunId = useCallback((id) => {
    _setActiveRunId(id);
    lsSet(LS_RUN, id);
  }, []);

  // Auto-load the latest optimization run on startup (if none persisted yet)
  useEffect(() => {
    optimizationService.listRuns()
      .then((res) => {
        // API interceptor already unwraps response.data, so res = body directly
        const runs = Array.isArray(res) ? res : (res?.runs ?? []);
        if (runs.length > 0 && !lsGet(LS_RUN)) {
          setActiveRunId(runs[0].run_id);
        }
      })
      .catch(() => {/* no runs yet */});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addNotification = useCallback((type, message) => {
    const id = Date.now();
    setNotifications((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 5000);
  }, []);

  const value = {
    activeScenarioId,
    setActiveScenarioId,
    activeRunId,
    setActiveRunId,
    compareRunId,
    setCompareRunId,
    notifications,
    addNotification,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppContext() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
}

export default AppContext;
