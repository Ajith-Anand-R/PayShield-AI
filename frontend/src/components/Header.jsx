import { Shield, Server, Activity } from "lucide-react";

const tabs = [
  { id: "feed", label: "Feed" },
  { id: "profile", label: "Profile" },
  { id: "graph", label: "Graph" },
  { id: "cases", label: "Cases" },
  { id: "stats", label: "Stats" },
];

export default function Header({ activeTab, onTabChange, serverStatus, streamStatus, onToggleStream }) {
  const statusMap = {
    online: { label: "Online", color: "text-mint", dotBg: "bg-mint" },
    connecting: { label: "Connecting", color: "text-saffron", dotBg: "bg-saffron" },
    offline: { label: "Offline", color: "text-ember", dotBg: "bg-ember" },
  };
  const status = statusMap[serverStatus] || statusMap.connecting;

  const isRunning = streamStatus?.running ?? false;
  const tps =
    streamStatus?.uptime_seconds > 0
      ? (streamStatus.total_generated / streamStatus.uptime_seconds).toFixed(1)
      : "0.0";

  return (
    <header className="sticky top-0 z-45 border-b border-white/5 bg-ink/70 backdrop-blur-xl shadow-[0_4px_30px_rgba(0,0,0,0.1)]">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-saffron/40 bg-saffron/10 text-saffron shadow-glow-saffron transition-all hover:scale-105">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <p className="font-display text-xl font-extrabold tracking-tight text-paper select-none">PayShield</p>
            <p className="text-[10px] uppercase tracking-[0.25em] text-mist">Pre-Transaction Risk Mesh</p>
          </div>
        </div>

        <nav className="flex flex-wrap items-center gap-2 bg-steel/20 border border-white/5 p-1 rounded-full">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider transition-all duration-300 active:scale-95 ${
                activeTab === tab.id
                  ? "bg-saffron text-ink font-bold shadow-glow-saffron"
                  : "text-mist hover:text-paper hover:bg-white/5"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {/* Gateway Status */}
          <div className="flex items-center gap-2.5 rounded-full border border-white/5 bg-carbon/50 px-3.5 py-1.5 text-xs shadow-inner">
            <Server className="h-3.5 w-3.5 text-mist" />
            <span className="text-mist">Gateway</span>
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${status.dotBg} animate-breathe`} />
              <span className={`font-semibold ${status.color}`}>{status.label}</span>
            </div>
          </div>

          {/* Stream Status Widget */}
          <button
            onClick={onToggleStream}
            className={`flex items-center gap-2.5 rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-widest transition-all duration-300 active:scale-[0.97] ${
              isRunning
                ? "border-mint/40 bg-mint/10 text-mint hover:bg-mint/20 hover:shadow-[0_0_15px_rgba(93,228,199,0.15)]"
                : "border-gold/40 bg-gold/10 text-gold hover:bg-gold/20 hover:shadow-[0_0_15px_rgba(247,179,43,0.15)]"
            }`}
          >
            <span className="relative flex h-2 w-2">
              <span
                className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${
                  isRunning ? "bg-mint animate-ping" : "bg-gold animate-pulse"
                }`}
              />
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isRunning ? "bg-mint" : "bg-gold"}`} />
            </span>
            <span>{isRunning ? "LIVE" : "PAUSED"}</span>
            <span className="flex items-center gap-1 border-l border-white/10 pl-2.5">
              <Activity className="h-3 w-3" />
              <span className="font-mono">{tps}</span>
              <span className="text-mist/60 text-[9px]">tps</span>
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}
