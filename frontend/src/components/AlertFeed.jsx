import { AlertTriangle, Info, ShieldAlert } from "lucide-react";

const severityTheme = {
  LOW: {
    text: "text-mint border-mint/20 bg-mint/5",
    border: "border-l-mint",
    icon: Info,
    iconColor: "text-mint",
  },
  MEDIUM: {
    text: "text-saffron border-saffron/20 bg-saffron/5",
    border: "border-l-saffron",
    icon: AlertTriangle,
    iconColor: "text-saffron",
  },
  HIGH: {
    text: "text-lilac border-lilac/20 bg-lilac/5",
    border: "border-l-lilac",
    icon: AlertTriangle,
    iconColor: "text-lilac",
  },
  CRITICAL: {
    text: "text-ember border-ember/20 bg-ember/5",
    border: "border-l-ember",
    icon: ShieldAlert,
    iconColor: "text-ember animate-pulse",
  },
};

export default function AlertFeed({ alerts }) {
  return (
    <div className="glass-panel grain p-5">
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
        <h2 className="font-sans text-lg font-bold text-paper">Incident Alerts</h2>
        <span className="data-pill">Live stream</span>
      </div>

      <div className="space-y-3">
        {alerts.length === 0 && (
          <div className="rounded-xl border border-white/5 bg-carbon/40 p-5 text-sm text-mist text-center">
            No alerts yet. Trigger a scenario to populate the incident queue.
          </div>
        )}
        {alerts.map((alert) => {
          const theme = severityTheme[alert.severity] || severityTheme.LOW;
          const Icon = theme.icon;
          return (
            <div
              key={alert.id}
              className={`rounded-xl border border-white/5 bg-carbon/20 border-l-4 ${theme.border} p-4 transition-all duration-300 hover:bg-carbon/30`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon className={`h-4 w-4 ${theme.iconColor}`} />
                  <span className="text-[10px] uppercase tracking-[0.2em] text-mist font-bold">
                    Incident ID: {String(alert.id).length > 8 ? `${String(alert.id).slice(0, 8)}...` : alert.id}
                  </span>
                </div>
                <span className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded border ${theme.text}`}>
                  {alert.severity}
                </span>
              </div>
              <p className="mt-2.5 text-xs text-paper leading-relaxed font-semibold">{alert.reason}</p>
              <p className="mt-2 text-[10px] text-mist/60 font-mono">
                {new Date(alert.timestamp).toLocaleString()}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
