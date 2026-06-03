import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

const decisionStyle = {
  ALLOW: "text-mint drop-shadow-[0_0_10px_rgba(93,228,199,0.15)]",
  STEP_UP: "text-saffron drop-shadow-[0_0_10px_rgba(247,179,43,0.15)]",
  DELAY: "text-lilac drop-shadow-[0_0_10px_rgba(179,146,240,0.15)]",
  BLOCK: "text-ember drop-shadow-[0_0_10px_rgba(255,92,92,0.15)]",
};

const formatReason = (reason) => reason.replace(/_/g, " ").toLowerCase();

export default function RiskScorePanel({ transaction }) {
  const scores = transaction?.breakdown;
  const radarData = scores
    ? [
        { subject: "Behavioral", score: scores.behavioral_score },
        { subject: "Device", score: scores.device_score },
        { subject: "Transaction", score: scores.anomaly_score },
        { subject: "Graph", score: scores.graph_score },
      ]
    : [];

  return (
    <div className="glass-panel grain p-6 shadow-xl">
      <div className="flex items-center justify-between border-b border-white/5 pb-4 mb-4">
        <h2 className="font-display text-lg font-bold text-paper">Risk Profile</h2>
        <span className="data-pill">Weights 20/25/35/20</span>
      </div>

      {!transaction ? (
        <div className="rounded-xl border border-white/5 bg-carbon/40 p-6 text-sm text-mist text-center">
          Select a transaction to view the risk breakdown.
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-mist">Decision</p>
              <p className={`font-display text-3xl font-black ${decisionStyle[transaction.decision]} mt-1`}>
                {transaction.decision}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-mist">Total Score</p>
              <p className="font-mono text-4xl font-black text-paper mt-1">{transaction.risk_score}</p>
            </div>
          </div>

          <div className="h-52 rounded-xl bg-carbon/20 border border-white/5 p-2 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData}>
                <PolarGrid stroke="#2A3344" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#94A3B8", fontSize: 10, fontWeight: 600 }} />
                <PolarRadiusAxis tick={{ fill: "#94A3B8", fontSize: 9 }} />
                <Radar dataKey="score" stroke="#F7B32B" fill="#F7B32B" fillOpacity={0.20} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-mist">Reason Codes</p>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {transaction.reason_codes?.length ? (
                transaction.reason_codes.map((reason) => (
                  <span
                    key={reason}
                    className="rounded-full border border-white/5 bg-carbon/60 px-3 py-1 text-[9px] font-bold uppercase tracking-widest text-paper hover:border-white/10 transition"
                  >
                    {formatReason(reason)}
                  </span>
                ))
              ) : (
                <span className="text-xs text-mist font-semibold">No flags triggered.</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

