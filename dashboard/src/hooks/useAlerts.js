import { useState, useEffect, useCallback } from 'react';
import { fetchAlerts, fetchHealth } from '../lib/api';

export function useAlerts(pollInterval = 4000) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [apiOnline, setApiOnline] = useState(null);

  const load = useCallback(async () => {
    try {
      const [data, health] = await Promise.all([fetchAlerts(), fetchHealth()]);
      setAlerts(data.sort((a, b) => new Date(b.detectedAt) - new Date(a.detectedAt)));
      setApiOnline(health.status === 'UP');
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      setError(e.message);
      setApiOnline(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, pollInterval);
    return () => clearInterval(id);
  }, [load, pollInterval]);

  return { alerts, loading, error, lastUpdated, apiOnline, refresh: load };
}
