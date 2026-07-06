import { Shield, Server, LogOut, Terminal, Search, User, Network, Briefcase, BarChart3 } from "lucide-react";

const tabs = [
  { id: "feed", label: "Scoring Console", icon: Terminal },
  { id: "investigation", label: "Investigation", icon: Search },
  { id: "profile", label: "User Dynamics", icon: User },
  { id: "graph", label: "Fraud Network", icon: Network },
  { id: "cases", label: "Cases", icon: Briefcase },
  { id: "stats", label: "Diagnostics", icon: BarChart3 },
];

export default function Header({ activeTab, onTabChange, serverStatus, currentUser, onLogout }) {
  const statusMap = {
    online: { label: "Online", color: "text-primary", dotBg: "bg-primary" },
    connecting: { label: "Connecting", color: "text-saffron", dotBg: "bg-saffron" },
    offline: { label: "Offline", color: "text-red-500", dotBg: "bg-red-500" },
  };
  const status = statusMap[serverStatus] || statusMap.connecting;

  return (
    <div className="w-full max-w-7xl mx-auto px-4 md:px-6 pt-4">
      <header className="rounded-2xl border border-white/5 bg-carbon/40 backdrop-blur-xl shadow-[0_8px_32px_0_rgba(0,0,0,0.3)] px-6 py-3 flex flex-wrap items-center justify-between gap-4">
        {/* Brand logo left */}
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary shadow-glow-primary transition-all duration-300 hover:scale-105 active:scale-95">
            <Shield className="h-4.5 w-4.5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-[9px] uppercase tracking-[0.25em] text-primary font-bold">SHIELD MESH</span>
            </div>
            <h1 className="font-sans text-sm font-black tracking-tight text-paper mt-0.5 leading-none">PayShield</h1>
          </div>
        </div>

        {/* Floating Navigation Dock */}
        <nav className="flex flex-wrap items-center gap-1 bg-white/5 border border-white/5 p-1 rounded-xl">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-300 active:scale-95 cursor-pointer ${
                  isActive
                    ? "bg-primary text-ink shadow-glow-primary font-extrabold"
                    : "text-mist hover:text-paper hover:bg-white/5"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Right Actions */}
        <div className="flex items-center gap-3">
          {/* Server Status Pill */}
          <div className="flex items-center gap-2 rounded-xl border border-white/5 bg-ink/40 px-3 py-1.5 text-[10px] font-mono shadow-inner">
            <Server className="h-3.5 w-3.5 text-mist" />
            <span className="text-mist font-semibold">Gateway:</span>
            <div className="flex items-center gap-1">
              <span className={`h-1.5 w-1.5 rounded-full ${status.dotBg} animate-breathe`} />
              <span className={`font-bold ${status.color}`}>{status.label}</span>
            </div>
          </div>

          {currentUser && (
            <button
              onClick={onLogout}
              className="flex items-center gap-1.5 rounded-xl border border-ember/25 bg-ember/5 hover:bg-ember/15 px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-ember transition-all duration-200 active:scale-95 cursor-pointer"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span>Exit</span>
            </button>
          )}
        </div>
      </header>
    </div>
  );
}
