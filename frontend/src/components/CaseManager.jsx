const severityTone = {
  LOW: "text-mint border-mint/30 bg-mint/5",
  MEDIUM: "text-saffron border-saffron/30 bg-saffron/5",
  HIGH: "text-lilac border-lilac/30 bg-lilac/5",
  CRITICAL: "text-ember border-ember/30 bg-ember/5",
};

function SeverityBadge({ severity }) {
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-wider ${severityTone[severity] || "border-steel/60 text-mist bg-steel/10"}`}>
      {severity}
    </span>
  );
}

export default function CaseManager({ cases, onUpdateCase }) {
  return (
    <div className="glass-panel grain p-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
        <h2 className="font-display text-lg font-bold text-paper">Active Fraud Cases</h2>
        <span className="data-pill font-bold">Compliance Node</span>
      </div>
      <div className="mt-4 overflow-x-auto pr-1">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-mist/60 border-b border-white/5 uppercase tracking-wider text-[9px] font-bold">
              <th className="pb-3">Case ID</th>
              <th className="pb-3">User</th>
              <th className="pb-3">Type</th>
              <th className="pb-3">Severity</th>
              <th className="pb-3">Opened</th>
              <th className="pb-3">Status</th>
              <th className="pb-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.03]">
            {cases.map((c) => (
              <tr key={c.id} className="hover:bg-white/[0.01] transition-colors">
                <td className="py-4 font-mono font-bold text-paper">{c.id.slice(0, 8)}...</td>
                <td className="py-4 text-mist font-semibold">{c.user_id}</td>
                <td className="py-4 uppercase text-[10px] text-paper font-semibold tracking-wider">{c.case_type}</td>
                <td className="py-4"><SeverityBadge severity={c.severity} /></td>
                <td className="py-4 text-mist font-medium">{new Date(c.opened_at).toLocaleString()}</td>
                <td className="py-4 font-semibold uppercase text-[10px] text-saffron">{c.outcome}</td>
                <td className="py-4 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => onUpdateCase(c.id, "confirmed")}
                      className="rounded-full border border-mint/45 bg-mint/5 px-3 py-1 text-[9px] font-bold uppercase tracking-widest text-mint hover:bg-mint hover:text-ink transition active:scale-95"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => onUpdateCase(c.id, "false_positive")}
                      className="rounded-full border border-ember/45 bg-ember/5 px-3 py-1 text-[9px] font-bold uppercase tracking-widest text-ember hover:bg-ember hover:text-ink transition active:scale-95"
                    >
                      FP
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {cases.length === 0 && (
              <tr>
                <td colSpan="7" className="py-8 text-center text-mist/50 font-medium">
                  No active cases under review.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

