import { useState, useMemo } from "react";

const logTone = {
  SYSTEM_INFO: "text-mint",
  SYSTEM_ERROR: "text-ember font-bold",
  TRANSACTION_SCORED: "text-cobalt",
  ALERT_CRITICAL: "text-ember drop-shadow-[0_0_8px_rgba(255,92,92,0.3)] font-bold",
  ALERT_HIGH: "text-saffron drop-shadow-[0_0_8px_rgba(247,179,43,0.3)] font-bold",
};

const FILTERS = [
  { id: "ALL", label: "All", types: null },
  { id: "ALERTS", label: "Alerts", types: ["ALERT_CRITICAL", "ALERT_HIGH", "TRANSACTION_SCORED"] },
  { id: "SYSTEM", label: "System", types: ["SYSTEM_INFO"] },
  { id: "ERRORS", label: "Errors", types: ["SYSTEM_ERROR"] },
];

export default function TerminalConsole({ logs }) {
  const [activeFilter, setActiveFilter] = useState("ALL");

  const filteredLogs = useMemo(() => {
    const filter = FILTERS.find((f) => f.id === activeFilter);
    if (!filter || !filter.types) return logs;
    return logs.filter((log) => filter.types.includes(log.type));
  }, [logs, activeFilter]);

  return (
    <div className="glass-panel grain p-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
        <h2 className="font-display text-lg font-bold text-paper">Security Gateway Console</h2>
        <span className="data-pill font-bold">SSE Traffic</span>
      </div>

      {/* ── Filter Buttons ────────────────────────────── */}
      <div className="flex items-center gap-1.5 mb-3">
        {FILTERS.map((filter) => (
          <button
            key={filter.id}
            onClick={() => setActiveFilter(filter.id)}
            className={`rounded-full px-3 py-1 text-[9px] font-bold uppercase tracking-widest transition-all duration-200 active:scale-95 ${
              activeFilter === filter.id
                ? "bg-mint/15 text-mint border border-mint/30"
                : "border border-white/5 text-mist hover:text-paper hover:bg-white/5"
            }`}
          >
            {filter.label}
          </button>
        ))}
        {activeFilter !== "ALL" && (
          <span className="ml-auto text-[9px] font-mono text-mist/50">
            {filteredLogs.length}/{logs.length}
          </span>
        )}
      </div>

      <div className="max-h-64 overflow-y-auto rounded-xl border border-white/5 bg-[#090B10]/90 p-4 font-mono text-[10.5px] leading-relaxed text-mist shadow-inner select-text">
        {filteredLogs.length === 0 && <p className="text-mist/50 animate-pulse">Initializing socket stream... waiting for gateway events...</p>}
        {filteredLogs.map((log, idx) => (
          <div key={`${log.timestamp}-${idx}`} className="mb-2 flex gap-3 border-b border-white/[0.02] pb-1.5 last:border-0 last:pb-0">
            <span className="text-mist/40 select-none font-bold">[{log.timestamp}]</span>
            <span className={`${logTone[log.type] || "text-paper"}`}>{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
