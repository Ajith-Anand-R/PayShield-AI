import { useEffect, useState } from "react";
import { Clock, Cpu, BarChart3, Activity, Layers, RefreshCw } from "lucide-react";

export default function DiagnosticsPanel({ apiBase }) {
  const [latency, setLatency] = useState({ p50: 0, p95: 0, p99: 0, count: 0 });
  const [models, setModels] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const [latRes, modelRes] = await Promise.all([
        fetch(`${apiBase}/dashboard/metrics/latency`),
        fetch(`${apiBase}/dashboard/metrics/model`)
      ]);

      if (latRes.ok && modelRes.ok) {
        setLatency(await latRes.json());
        setModels(await modelRes.json());
      } else {
        setError("Failed to fetch diagnostics from gateway.");
      }
    } catch (err) {
      setError("Network error communicating with gateway.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 10000);
    return () => clearInterval(interval);
  }, [apiBase]);

  const formatMetric = (val) => {
    if (val === undefined || val === null) return "N/A";
    if (typeof val === "number") return val.toFixed(3);
    return val;
  };

  const getMetricPercent = (val) => {
    if (typeof val !== "number") return 0;
    return val <= 1 ? val * 100 : val;
  };

  return (
    <div className="space-y-6">
      {/* Header and Refresh Button */}
      <div className="flex items-center justify-between border-b border-white/5 pb-4">
        <div>
          <h2 className="font-sans text-xl font-bold text-paper">System Diagnostics & ML Observability</h2>
          <p className="text-xs text-mist mt-1">Real-time gateway performance metrics and calibrated classifier validation stats.</p>
        </div>
        <button
          onClick={fetchMetrics}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-mist hover:text-paper transition active:scale-95 cursor-pointer disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400 flex items-center gap-2">
          <span>⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {/* Latency Section */}
      <div className="grid gap-6 md:grid-cols-12">
        <div className="md:col-span-4 glass-panel grain p-6 flex flex-col justify-between shadow-lg">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-[0.2em] text-mist font-bold">Total Scored Events</span>
              <Activity className="h-4 w-4 text-mint opacity-70" />
            </div>
            <p className="mt-4 font-mono text-4xl font-black text-paper">{latency.count}</p>
          </div>
          <p className="text-[10px] text-mist mt-6 leading-relaxed">
            Total number of live transactional decisions processed by PayShield scoring gateway since server startup.
          </p>
        </div>

        <div className="md:col-span-8 glass-panel grain p-6 shadow-lg">
          <div className="flex items-center justify-between border-b border-white/5 pb-3 mb-4">
            <span className="text-[10px] uppercase tracking-[0.2em] text-mist font-bold">Scoring Latency (Measured)</span>
            <Clock className="h-4 w-4 text-cobalt opacity-70" />
          </div>

          <div className="grid grid-cols-3 gap-4">
            {/* Median */}
            <div className="border border-white/5 bg-carbon/20 rounded-xl p-4 flex flex-col justify-between">
              <div>
                <span className="text-[8px] uppercase tracking-wider text-mist font-bold">p50 (Median)</span>
                <p className="mt-2 font-mono text-2xl font-bold text-mint">{latency.p50} <span className="text-xs font-sans text-mist">ms</span></p>
              </div>
              <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mt-4">
                <div className="bg-mint h-full rounded-full" style={{ width: `${Math.min((latency.p50 / 50) * 100, 100)}%` }} />
              </div>
            </div>

            {/* p95 */}
            <div className="border border-white/5 bg-carbon/20 rounded-xl p-4 flex flex-col justify-between">
              <div>
                <span className="text-[8px] uppercase tracking-wider text-mist font-bold">p95 Percentile</span>
                <p className="mt-2 font-mono text-2xl font-bold text-saffron">{latency.p95} <span className="text-xs font-sans text-mist">ms</span></p>
              </div>
              <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mt-4">
                <div className="bg-saffron h-full rounded-full" style={{ width: `${Math.min((latency.p95 / 50) * 100, 100)}%` }} />
              </div>
            </div>

            {/* p99 */}
            <div className="border border-white/5 bg-carbon/20 rounded-xl p-4 flex flex-col justify-between">
              <div>
                <span className="text-[8px] uppercase tracking-wider text-mist font-bold">p99 (Tail)</span>
                <p className="mt-2 font-mono text-2xl font-bold text-rose-400">{latency.p99} <span className="text-xs font-sans text-mist">ms</span></p>
              </div>
              <div className="w-full bg-white/5 h-1.5 rounded-full overflow-hidden mt-4">
                <div className="bg-rose-400 h-full rounded-full" style={{ width: `${Math.min((latency.p99 / 50) * 100, 100)}%` }} />
              </div>
            </div>
          </div>
          <p className="text-[9px] text-mist/60 mt-4 italic">
            * Benchmark target is &lt; 50ms p95 latency under concurrent loads.
          </p>
        </div>
      </div>

      {/* Model Performance Section */}
      <div>
        <div className="flex items-center justify-between border-b border-white/5 pb-3 mb-4">
          <span className="text-[10px] uppercase tracking-[0.2em] text-mist font-bold">Active ML Classifier Validation Metrics</span>
          <Cpu className="h-4 w-4 text-saffron opacity-70" />
        </div>

        {Object.keys(models).length === 0 ? (
          <div className="rounded-xl border border-white/5 bg-carbon/40 p-8 text-center text-sm text-mist">
            No active ML models found. Start retraining or check backend database connections.
          </div>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(models).map(([name, info]) => (
              <div key={name} className="glass-panel grain p-5 shadow-md flex flex-col justify-between">
                <div>
                  {/* Model header */}
                  <div className="flex items-start justify-between border-b border-white/5 pb-2.5 mb-3.5">
                    <div>
                      <h4 className="text-xs font-bold text-paper uppercase tracking-wider">{name.replace("_", " ")} Engine</h4>
                      <p className="text-[8px] font-mono text-mist mt-0.5">Version: {info.version}</p>
                    </div>
                    <span className="rounded-full bg-mint/10 border border-mint/20 text-mint px-2 py-0.5 text-[8px] font-extrabold uppercase">
                      Active
                    </span>
                  </div>

                  {/* Metrics details */}
                  <div className="space-y-2">
                    {Object.entries(info.metrics || {}).map(([metricKey, metricValue]) => {
                      const percent = getMetricPercent(metricValue);
                      return (
                        <div key={metricKey} className="space-y-1">
                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-mist font-semibold capitalize">{metricKey.replace("_", " ")}</span>
                            <span className="font-mono text-paper font-bold">{formatMetric(metricValue)}</span>
                          </div>
                          {typeof metricValue === "number" && (
                            <div className="w-full bg-white/5 h-1 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  percent > 85 ? "bg-mint" : percent > 60 ? "bg-saffron" : "bg-rose-400"
                                }`}
                                style={{ width: `${percent}%` }}
                              />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-white/5 flex items-center justify-between text-[8px] text-mist/60 font-mono">
                  <span>Trained at:</span>
                  <span>{info.trained_at ? new Date(info.trained_at).toLocaleString() : "—"}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
