import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { Play, Square, Zap, AlertTriangle, Clock, Activity } from "lucide-react";

/* ── helpers ─────────────────────────────────────────────── */
function formatUptime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function useDebounce(callback, delay) {
  const timer = useRef(null);
  const stableCallback = useRef(callback);
  stableCallback.current = callback;

  return useCallback(
    (...args) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => stableCallback.current(...args), delay);
    },
    [delay]
  );
}

/* ── component ───────────────────────────────────────────── */
export default function LiveMonitor({ streamStatus, onStartStream, onStopStream, onUpdateConfig }) {
  const running = streamStatus?.running ?? false;
  const speed = streamStatus?.speed ?? 3.0;
  const fraudRate = streamStatus?.fraud_rate ?? 0.08;

  const [localSpeed, setLocalSpeed] = useState(speed);
  const [localFraud, setLocalFraud] = useState(fraudRate);

  /* sync from parent when stream status updates externally */
  useEffect(() => { setLocalSpeed(speed); }, [speed]);
  useEffect(() => { setLocalFraud(fraudRate); }, [fraudRate]);

  const debouncedUpdate = useDebounce((config) => {
    onUpdateConfig(config);
  }, 300);

  const handleSpeedChange = (e) => {
    const val = parseFloat(e.target.value);
    setLocalSpeed(val);
    debouncedUpdate({ speed: val });
  };

  const handleFraudChange = (e) => {
    const val = parseFloat(e.target.value);
    setLocalFraud(val);
    debouncedUpdate({ fraud_rate: val });
  };

  /* ticking counter for total_generated */
  const [displayCount, setDisplayCount] = useState(streamStatus?.total_generated ?? 0);
  const targetCount = streamStatus?.total_generated ?? 0;

  useEffect(() => {
    if (displayCount === targetCount) return;
    const step = targetCount > displayCount ? 1 : -1;
    const interval = setInterval(() => {
      setDisplayCount((prev) => {
        if (prev === targetCount) { clearInterval(interval); return prev; }
        const next = prev + step;
        if ((step > 0 && next >= targetCount) || (step < 0 && next <= targetCount)) {
          clearInterval(interval);
          return targetCount;
        }
        return next;
      });
    }, 30);
    return () => clearInterval(interval);
  }, [targetCount, displayCount]);

  const metrics = useMemo(() => [
    {
      label: "Total Processed",
      value: displayCount.toLocaleString("en-IN"),
      icon: Activity,
      color: "text-paper",
    },
    {
      label: "Blocked",
      value: (streamStatus?.total_blocked ?? 0).toLocaleString("en-IN"),
      icon: AlertTriangle,
      color: "text-ember",
    },
    {
      label: "Fraud Injected",
      value: (streamStatus?.total_fraud_injected ?? 0).toLocaleString("en-IN"),
      icon: Zap,
      color: "text-gold",
    },
    {
      label: "Uptime",
      value: formatUptime(streamStatus?.uptime_seconds ?? 0),
      icon: Clock,
      color: "text-lilac",
    },
  ], [displayCount, streamStatus]);

  return (
    <div className="glass-panel grain p-6 shadow-xl transition-all duration-300">
      {/* ── Header ────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-5">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                running ? "bg-mint animate-ping" : "bg-gold animate-pulse"
              }`}
            />
            <span
              className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                running ? "bg-mint" : "bg-gold"
              }`}
            />
          </span>
          <h2 className="font-display text-lg font-bold text-paper">Live Transaction Stream</h2>
        </div>
        <span className={`data-pill font-bold ${running ? "text-mint" : "text-gold"}`}>
          {running ? "STREAMING" : "PAUSED"}
        </span>
      </div>

      {/* ── Toggle + Sliders Row ──────────────────────── */}
      <div className="flex flex-col sm:flex-row gap-5 items-start">
        {/* Start / Stop Button */}
        <button
          onClick={running ? onStopStream : onStartStream}
          className={`group relative flex items-center justify-center gap-2.5 rounded-xl px-6 py-3.5 text-sm font-bold uppercase tracking-widest transition-all duration-300 active:scale-[0.96] ${
            running
              ? "border border-ember/50 bg-ember/10 text-ember hover:bg-ember/20 shadow-[0_0_20px_rgba(255,92,92,0.15)]"
              : "border border-mint/50 bg-mint/10 text-mint hover:bg-mint/20 shadow-[0_0_20px_rgba(93,228,199,0.15)]"
          }`}
        >
          {running ? (
            <Square className="h-4 w-4 transition-transform group-hover:scale-110" />
          ) : (
            <Play className="h-4 w-4 transition-transform group-hover:scale-110" />
          )}
          {running ? "Stop" : "Start"}
        </button>

        {/* Sliders */}
        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-4 w-full">
          {/* Speed Slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[10px] uppercase tracking-[0.2em] text-mist font-semibold">Interval</label>
              <span className="font-mono text-xs text-paper font-bold">{localSpeed.toFixed(1)}s</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="10"
              step="0.5"
              value={localSpeed}
              onChange={handleSpeedChange}
              className="w-full h-1.5 rounded-full appearance-none bg-white/10 cursor-pointer accent-mint
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-mint [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(93,228,199,0.4)]
                [&::-webkit-slider-thumb]:transition-all [&::-webkit-slider-thumb]:hover:scale-125"
            />
            <div className="flex justify-between text-[9px] text-mist/50">
              <span>0.5s</span><span>10s</span>
            </div>
          </div>

          {/* Fraud Rate Slider */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-[10px] uppercase tracking-[0.2em] text-mist font-semibold">Fraud Injection</label>
              <span className="font-mono text-xs text-gold font-bold">{(localFraud * 100).toFixed(0)}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="0.3"
              step="0.01"
              value={localFraud}
              onChange={handleFraudChange}
              className="w-full h-1.5 rounded-full appearance-none bg-white/10 cursor-pointer accent-gold
                [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4
                [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-gold [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(247,179,43,0.4)]
                [&::-webkit-slider-thumb]:transition-all [&::-webkit-slider-thumb]:hover:scale-125"
            />
            <div className="flex justify-between text-[9px] text-mist/50">
              <span>0%</span><span>30%</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Live Metrics Bar ──────────────────────────── */}
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="rounded-xl border border-white/5 bg-carbon/40 px-4 py-3 text-center transition-all duration-200 hover:border-white/10"
          >
            <div className="flex items-center justify-center gap-1.5 mb-1.5">
              <m.icon className={`h-3 w-3 ${m.color}`} />
              <p className="text-[9px] uppercase tracking-[0.2em] text-mist font-semibold">{m.label}</p>
            </div>
            <p className={`font-mono text-xl font-bold ${m.color} transition-all duration-200`}>{m.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
