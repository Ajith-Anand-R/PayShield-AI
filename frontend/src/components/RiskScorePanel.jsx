import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from "recharts";

const decisionStyle = {
  APPROVE: "text-mint drop-shadow-[0_0_10px_rgba(93,228,199,0.15)]",
  REVIEW: "text-saffron drop-shadow-[0_0_10px_rgba(247,179,43,0.15)]",
  HOLD: "text-ember drop-shadow-[0_0_10px_rgba(255,92,92,0.15)]",
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
        { subject: "Geolocation", score: scores.geolocation_score },
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
                <Radar dataKey="score" stroke="#10b981" fill="#10b981" fillOpacity={0.25} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-mist">Reason Codes & Insights</p>
            <div className="mt-2.5 space-y-2">
              {transaction.reasons_detailed?.length ? (
                transaction.reasons_detailed.map((reason) => {
                  const severityColors = {
                    CRITICAL: "border-red-500/20 bg-red-500/5 text-red-400",
                    WARNING: "border-saffron/20 bg-saffron/5 text-saffron",
                    INFO: "border-mint/20 bg-mint/5 text-mint"
                  };
                  const colorClass = severityColors[reason.severity] || "border-white/5 bg-carbon/40 text-paper";
                  return (
                    <div
                      key={reason.code}
                      className={`rounded-lg border p-2.5 text-xs flex flex-col space-y-1 hover:border-white/10 transition ${colorClass}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold tracking-wider text-[10px] uppercase">{formatReason(reason.code)}</span>
                        <span className="text-[8px] uppercase tracking-widest px-1.5 py-0.5 rounded-full bg-white/5 font-extrabold opacity-75">{reason.signal}</span>
                      </div>
                      <span className="text-mist text-[11px] font-medium leading-relaxed">{reason.human_message}</span>
                    </div>
                  );
                })
              ) : transaction.reason_codes?.length ? (
                transaction.reason_codes.map((reason) => {
                  const explanations = {
                    BOT_PATTERN_DETECTED: "Automated/BOT interaction pattern detected.",
                    BEHAVIORAL_DEVIATION: "Keystroke/mouse dynamics deviate from baseline.",
                    NEW_DEVICE: "New device fingerprint never seen before for this user.",
                    COMPROMISED_DEVICE_IP: "Known compromised device or untrusted IP.",
                    SUSPICIOUS_IP_LOC: "Suspicious location change or network provider.",
                    IMPOSSIBLE_TRAVEL: "Impossible travel velocity detected.",
                    SUSPICIOUS_COUNTRY_CHANGE: "Sudden change in transaction country.",
                    SUSPICIOUS_CITY_CHANGE: "Sudden change in transaction city.",
                    SCAM_TEXT_DETECTED: "Remarks classified as high scam risk by Gemini AI.",
                    SUSPICIOUS_REMARKS: "Transfer remarks show suspicious intent patterns.",
                    EXTREME_ANOMALY_VELOCITY: "Highly anomalous transaction count/velocity.",
                    VELOCITY_BURST_DETECTED: "Burst of transactions within a short window.",
                    HIGH_AMOUNT: "Transaction amount exceeds usual threshold.",
                    CIRCULAR_MONEY_FLOW: "Part of a circular fund routing path (mule behavior).",
                    LAYERING_PATTERN: "Transfers show layering pattern over multiple hops.",
                    BURST_TRANSFERS: "Frequent burst transfers detected.",
                    HUB_ACCOUNT: "Account acts as a hub sending to many beneficiaries.",
                    FUNNEL_ACCOUNT: "Account acts as a funnel pooling funds.",
                    FRAUD_RING_LINK: "Direct link to a known fraudulent account/device.",
                    SHARED_COMPROMISED_DEVICE: "Device is shared with a flagged fraudster account.",
                    SUSPICIOUS_RISK_AGGREGATION: "Aggregated risk indicators exceed safety threshold."
                  };
                  const expl = explanations[reason] || formatReason(reason);
                  return (
                    <div
                      key={reason}
                      className="rounded-lg border border-white/5 bg-carbon/40 p-2.5 text-xs text-paper flex flex-col space-y-1 hover:border-white/10 transition"
                    >
                      <span className="font-bold tracking-wider text-[10px] text-saffron uppercase">{formatReason(reason)}</span>
                      <span className="text-mist text-[11px] font-medium leading-relaxed">{expl}</span>
                    </div>
                  );
                })
              ) : (
                <span className="text-xs text-mist font-semibold">No risk flags triggered.</span>
              )}
            </div>
          </div>

          {transaction.remarks && (
            <div className="border-t border-white/5 pt-4">
              <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-mist">Transaction Remarks</p>
              <p className="mt-1.5 text-xs italic text-paper font-mono">"{transaction.remarks}"</p>
            </div>
          )}

          {transaction.scam_classification && (
            <div className={`mt-4 rounded-lg border p-3.5 ${
              transaction.scam_classification === "Scam Likely"
                ? "border-ember/30 bg-ember/10"
                : transaction.scam_classification === "Suspicious"
                ? "border-saffron/30 bg-saffron/10"
                : "border-mint/20 bg-mint/5"
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-paper">Gemini Scam Classification</span>
                <span className={`text-[9px] font-extrabold uppercase px-2 py-0.5 rounded-full ${
                  transaction.scam_classification === "Scam Likely"
                    ? "bg-ember text-paper"
                    : transaction.scam_classification === "Suspicious"
                    ? "bg-saffron text-carbon"
                    : "bg-mint text-carbon"
                }`}>
                  {transaction.scam_classification}
                </span>
              </div>
              {transaction.scam_explanation && (
                <p className="mt-2 text-[11px] leading-relaxed text-mist">
                  {transaction.scam_explanation}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

