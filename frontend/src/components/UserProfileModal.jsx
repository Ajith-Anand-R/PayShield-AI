import { User, Activity, Laptop, Shield, Calendar } from "lucide-react";

export default function UserProfileModal({ profile }) {
  if (!profile) {
    return (
      <div className="glass-panel grain p-6 text-center text-mist">
        <User className="mx-auto h-8 w-8 text-mist/40 mb-2" />
        <h3 className="font-sans text-md font-bold text-paper">User Dynamics Console</h3>
        <p className="mt-2 text-xs text-mist">Select a scored transaction to view user baseline history.</p>
      </div>
    );
  }

  const currency = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });

  return (
    <div className="glass-panel grain p-8 space-y-8">
      {/* Header section */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/5 pb-6">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-primary/20 bg-primary/5 text-primary">
            <User className="h-6 w-6" />
          </div>
          <div>
            <span className="font-mono text-[9px] uppercase tracking-[0.25em] text-primary font-bold">USER IDENTITY BASES</span>
            <h2 className="text-xl font-bold tracking-tight text-paper mt-0.5">{profile.user.username}</h2>
            <p className="text-[10px] font-mono text-mist mt-0.5">ID: {profile.user.id}</p>
          </div>
        </div>
        <div className="data-pill">Verified Telemetry Profile</div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 py-2">
        <div className="flex flex-col">
          <span className="text-[9px] uppercase tracking-[0.2em] text-mist font-bold">Historical Audits</span>
          <span className="font-mono text-3xl font-black text-paper mt-1.5">{profile.stats.total_transactions}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase tracking-[0.2em] text-mist font-bold">Average Scored Amount</span>
          <span className="font-mono text-3xl font-black text-paper mt-1.5">{currency.format(profile.stats.avg_amount)}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase tracking-[0.2em] text-mist font-bold">Intercepted / Step-Ups</span>
          <span className="font-mono text-3xl font-black text-rose-400 mt-1.5">
            {profile.stats.blocked_count} <span className="text-mist text-lg font-normal">/</span> <span className="text-saffron">{profile.stats.step_up_count}</span>
          </span>
        </div>
      </div>

      <div className="grid gap-8 md:grid-cols-2 pt-4 border-t border-white/5">
        {/* Left column: Devices & Biometrics */}
        <div className="space-y-6">
          {/* Trusted Devices list */}
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-primary">
              <Laptop className="h-4 w-4" />
              <h3 className="text-xs font-bold uppercase tracking-wider font-mono">Registered Device Signatures</h3>
            </div>
            <div className="divide-y divide-white/5 border-t border-white/5">
              {profile.devices.map((device) => (
                <div key={device.hash} className="flex items-center justify-between py-2.5 text-xs">
                  <span className="font-mono text-mist">{device.hash}</span>
                  <span className={`inline-flex items-center gap-1 text-[10px] font-bold uppercase ${device.trusted ? "text-primary" : "text-rose-400"}`}>
                    <Shield className="h-3 w-3" />
                    {device.trusted ? "Trusted" : "Untrusted"}
                  </span>
                </div>
              ))}
              {profile.devices.length === 0 && (
                <p className="text-xs text-mist italic py-3">No device signatures registered.</p>
              )}
            </div>
          </div>

          {/* Biometrics baseline */}
          <div className="space-y-4 pt-4 border-t border-white/5">
            <div className="flex items-center gap-2 text-primary">
              <Activity className="h-4 w-4" />
              <h3 className="text-xs font-bold uppercase tracking-wider font-mono">Biometric DNA Baselines</h3>
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs">
              <div className="bg-carbon/25 border border-white/5 p-3.5 rounded-xl">
                <span className="text-[9px] uppercase tracking-wider text-mist">Avg Keystroke Dwell</span>
                <p className="mt-1 font-mono font-bold text-paper text-sm">
                  {profile.behavior_baseline.keystroke_dwell ? `${profile.behavior_baseline.keystroke_dwell.toFixed(3)}s` : "N/A"}
                </p>
              </div>
              <div className="bg-carbon/25 border border-white/5 p-3.5 rounded-xl">
                <span className="text-[9px] uppercase tracking-wider text-mist">Avg Mouse Move Speed</span>
                <p className="mt-1 font-mono font-bold text-paper text-sm">
                  {profile.behavior_baseline.mouse_speed ? `${profile.behavior_baseline.mouse_speed.toFixed(1)}px/s` : "N/A"}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right column: Recent Transactions history list */}
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-primary">
            <Calendar className="h-4 w-4" />
            <h3 className="text-xs font-bold uppercase tracking-wider font-mono">Recent Telemetry Audits</h3>
          </div>
          <div className="divide-y divide-white/5 border-t border-white/5">
            {profile.recent_transactions.map((tx) => (
              <div key={tx.id} className="flex items-center justify-between py-3 text-xs">
                <div className="space-y-0.5">
                  <p className="font-mono text-paper font-semibold">{tx.id.slice(0, 12)}...</p>
                  <p className="text-[9px] text-mist font-bold uppercase">Status: {tx.status}</p>
                </div>
                <span className="font-mono text-sm font-bold text-paper">{currency.format(tx.amount)}</span>
              </div>
            ))}
            {profile.recent_transactions.length === 0 && (
              <p className="text-xs text-mist italic py-3">No recent logs found.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
