import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";

const decisionStyle = {
  ALLOW: "bg-mint/10 text-mint border-mint/35",
  STEP_UP: "bg-saffron/10 text-saffron border-saffron/35",
  DELAY: "bg-lilac/10 text-lilac border-lilac/35",
  BLOCK: "bg-ember/10 text-ember border-ember/35",
};

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

export default function LiveFeed({ transactions, onSelect, selectedId }) {
  const containerRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  /* Auto-scroll to top when new transactions arrive */
  useEffect(() => {
    if (autoScroll && containerRef.current && transactions.length > 0) {
      containerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [transactions, autoScroll]);

  return (
    <div className="glass-panel grain p-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-mint opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-mint"></span>
          </span>
          <h2 className="font-display text-lg font-bold text-paper">Live Transaction Feed</h2>
          {transactions.length > 0 && (
            <span className="ml-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[9px] font-mono font-bold text-mist">
              {transactions.length} transactions
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[9px] font-bold uppercase tracking-widest transition-all duration-200 active:scale-95 ${
              autoScroll
                ? "border-mint/30 bg-mint/10 text-mint"
                : "border-gold/30 bg-gold/10 text-gold"
            }`}
          >
            {autoScroll ? (
              <Pause className="h-2.5 w-2.5" />
            ) : (
              <Play className="h-2.5 w-2.5" />
            )}
            {autoScroll ? "Auto" : "Paused"}
          </button>
          <span className="data-pill">Streaming</span>
        </div>
      </div>

      <div ref={containerRef} className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {transactions.length === 0 && (
          <div className="rounded-xl border border-white/5 bg-carbon/40 p-6 text-sm text-mist text-center">
            No transactions yet. Start the live stream to activate the feed.
          </div>
        )}
        {transactions.map((tx) => (
          <button
            key={tx.transaction_id}
            onClick={() => onSelect(tx)}
            className={`w-full rounded-xl border px-4 py-3.5 text-left transition-all duration-300 transform hover:-translate-y-0.5 active:scale-[0.98] ${
              selectedId === tx.transaction_id
                ? "border-saffron/60 bg-saffron/5 shadow-glow-saffron/5"
                : "border-white/5 bg-carbon/40 hover:border-white/10 hover:bg-carbon/60"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[10px] uppercase tracking-[0.25em] text-mist font-bold">User: {tx.user_id}</p>
                <p className="font-mono text-xl font-bold text-paper mt-1">{currency.format(tx.amount)}</p>
              </div>
              <div className={`rounded-full border px-3 py-1 text-[9px] font-bold uppercase tracking-widest ${decisionStyle[tx.decision]}`}>
                {tx.decision}
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-mist font-semibold">
              <span className="font-mono">Score: {tx.risk_score}</span>
              <span>{new Date(tx.timestamp).toLocaleTimeString()}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
