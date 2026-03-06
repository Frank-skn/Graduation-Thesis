import React, { createContext, useContext, useState, useCallback } from 'react';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [activeScenarioId, setActiveScenarioId] = useState(null);
  const [activeRunId, setActiveRunId] = useState(null);
  const [compareRunId, setCompareRunId] = useState(null);
  const [notifications, setNotifications] = useState([]);

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
