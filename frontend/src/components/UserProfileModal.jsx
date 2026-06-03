export default function UserProfileModal({ profile }) {
  if (!profile) {
    return (
      <div className="glass-panel grain p-6">
        <h2 className="font-display text-lg font-bold text-paper">User Profile</h2>
        <p className="mt-4 text-sm text-mist">Select a transaction to load user history.</p>
      </div>
    );
  }

  return (
    <div className="glass-panel grain p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-mist">User</p>
          <p className="font-display text-2xl font-bold text-paper">{profile.user.username}</p>
          <p className="text-xs text-mist">{profile.user.id}</p>
        </div>
        <div className="data-pill">Behavioral Baseline</div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-steel/60 bg-carbon/60 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-mist">Total Transactions</p>
          <p className="mt-2 font-display text-2xl font-bold text-paper">{profile.stats.total_transactions}</p>
        </div>
        <div className="rounded-xl border border-steel/60 bg-carbon/60 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-mist">Avg Amount</p>
          <p className="mt-2 font-display text-2xl font-bold text-paper">₹{profile.stats.avg_amount}</p>
        </div>
        <div className="rounded-xl border border-steel/60 bg-carbon/60 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-mist">Blocked / Step-Up</p>
          <p className="mt-2 font-display text-2xl font-bold text-paper">
            {profile.stats.blocked_count} / {profile.stats.step_up_count}
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-steel/60 bg-carbon/60 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-mist">Devices</p>
          <div className="mt-3 space-y-2 text-sm text-paper">
            {profile.devices.map((device) => (
              <div key={device.hash} className="flex items-center justify-between">
                <span className="font-mono text-xs">{device.hash}</span>
                <span className={`text-xs ${device.trusted ? "text-mint" : "text-ember"}`}>
                  {device.trusted ? "Trusted" : "Untrusted"}
                </span>
              </div>
            ))}
            {profile.devices.length === 0 && <span className="text-mist">No devices found.</span>}
          </div>
        </div>
        <div className="rounded-xl border border-steel/60 bg-carbon/60 p-4">
          <p className="text-xs uppercase tracking-[0.2em] text-mist">Behavior Baseline</p>
          <div className="mt-3 text-sm text-paper">
            <p>Keystroke dwell: {profile.behavior_baseline.keystroke_dwell ?? "N/A"}</p>
            <p>Mouse speed: {profile.behavior_baseline.mouse_speed ?? "N/A"}</p>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-steel/60 bg-carbon/60 p-4">
        <p className="text-xs uppercase tracking-[0.2em] text-mist">Recent Transactions</p>
        <div className="mt-3 space-y-2 text-sm text-paper">
          {profile.recent_transactions.map((tx) => (
            <div key={tx.id} className="flex items-center justify-between">
              <span className="font-mono text-xs">{tx.id.slice(0, 10)}...</span>
              <span>{tx.status}</span>
              <span>₹{tx.amount}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
