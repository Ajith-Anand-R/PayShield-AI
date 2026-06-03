import { useCallback, useEffect, useState } from "react";

export default function useGraphData(apiBase) {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });

  const refreshGraph = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/graph/data`);
      if (res.ok) {
        setGraphData(await res.json());
      }
    } catch (e) {
      // Ignore transient fetch errors
    }
  }, [apiBase]);

  useEffect(() => {
    refreshGraph();
    const interval = setInterval(refreshGraph, 12000);
    return () => clearInterval(interval);
  }, [refreshGraph]);

  return { graphData, refreshGraph };
}
