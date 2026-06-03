const scenarios = [
  {
    id: "ato",
    title: "Account Takeover",
    description:
      "New device from Nigeria at 3 AM. ₹95,000 sent to a beneficiary added 4 minutes ago.",
    expected: "BLOCK · score ~83",
  },
  {
    id: "fraud_ring",
    title: "Fraud Ring Detected",
    description:
      "Ring member attempts transfer using a device fingerprint shared with 4 compromised accounts.",
    expected: "DELAY/BLOCK · score ~72",
  },
  {
    id: "normal",
    title: "Safe Payment ✓",
    description:
      "Alice’s usual morning UPI transfer of ₹5,000 from her trusted MacBook.",
    expected: "ALLOW · score ~12",
  },
];

export default function ScenarioController({ onRunScenario, runningScenario }) {
  return (
    <div className="glass-panel grain p-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
        <h2 className="font-display text-lg font-bold text-paper">Scenario Controller</h2>
        <span className="data-pill font-bold">Demo Engine</span>
      </div>

      <div className="mt-4 grid gap-4 grid-cols-1 sm:grid-cols-3">
        {scenarios.map((scenario) => {
          const isActive = runningScenario === scenario.id;
          return (
            <div key={scenario.id} className="flex flex-col justify-between rounded-xl border border-white/5 bg-carbon/40 p-4 transition-all duration-300 hover:border-white/10 hover:bg-carbon/60">
              <div>
                <p className="font-display text-base font-bold text-paper tracking-tight">{scenario.title}</p>
                <p className="text-[11px] text-mist mt-1.5 leading-normal">{scenario.description}</p>
              </div>
              <div className="mt-4 pt-3 border-t border-white/5 flex flex-wrap items-center justify-between gap-2">
                <span className="text-[9px] font-bold uppercase tracking-widest text-mist">{scenario.expected}</span>
                <button
                  onClick={() => onRunScenario(scenario.id)}
                  className={`rounded-full px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-all duration-350 active:scale-[0.96] ${
                    isActive
                      ? "bg-steel text-paper cursor-not-allowed animate-pulse"
                      : "border border-saffron/45 bg-saffron/10 text-saffron hover:bg-saffron hover:text-ink hover:shadow-glow-saffron"
                  }`}
                  disabled={isActive}
                >
                  {isActive ? "Running" : "Trigger"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

