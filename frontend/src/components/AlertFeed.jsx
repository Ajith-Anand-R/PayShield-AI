const severityTone = {
  LOW: "text-mint",
  MEDIUM: "text-saffron",
  HIGH: "text-lilac",
  CRITICAL: "text-ember",
};

export default function AlertFeed({ alerts }) {
  return (
    <div className="glass-panel grain p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-bold text-paper">Incident Alerts</h2>
        <span className="data-pill">Live</span>
      </div>

      <div className="mt-4 space-y-3">
        {alerts.length === 0 && (
          <div className="rounded-xl border border-steel/60 bg-carbon/60 p-5 text-sm text-mist">
            No alerts yet. Trigger a scenario to populate the incident queue.
          </div>
        )}
        {alerts.map((alert) => (
          <div key={alert.id} className="rounded-xl border border-steel/60 bg-carbon/60 p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.2em] text-mist">Alert {alert.id}</span>
              <span className={`text-xs font-semibold ${severityTone[alert.severity]}`}>{alert.severity}</span>
            </div>
            <p className="mt-2 text-sm text-paper">{alert.reason}</p>
            <p className="mt-2 text-xs text-mist">{new Date(alert.timestamp).toLocaleString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
