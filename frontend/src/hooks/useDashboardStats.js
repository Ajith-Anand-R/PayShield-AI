import { useCallback, useEffect, useState } from "react";

export default function useDashboardStats(apiBase) {
  const [stats, setStats] = useState({
    total_transactions: 0,
    blocked: 0,
    step_up: 0,
    allowed: 0,
    block_rate: 0,
    false_positive_rate: 0,
  });

  const refreshStats = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/dashboard/stats`);
      if (res.ok) {
        setStats(await res.json());
      }
    } catch (e) {
      // Ignore transient fetch errors
    }
  }, [apiBase]);

  useEffect(() => {
    refreshStats();
    const interval = setInterval(refreshStats, 15000);
    return () => clearInterval(interval);
  }, [refreshStats]);

  return { stats, refreshStats };
}
