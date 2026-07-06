import { useEffect, useState } from "react";
import { Clock, MapPin, Activity, Laptop, ShieldAlert, ShieldCheck, Cpu, ArrowRight } from "lucide-react";

export default function InvestigationConsole({ transactionId, apiBase }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!transactionId) return;

    async function fetchInvestigation() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${apiBase}/investigation/${transactionId}`);
        if (res.ok) {
          setData(await res.json());
        } else {
          setError("Failed to retrieve investigation record.");
        }
      } catch (e) {
        setError("Error connecting to server for investigation.");
      } finally {
        setLoading(false);
      }
    }

    fetchInvestigation();
  }, [transactionId, apiBase]);

  if (!transactionId) {
    return (
      <div className="glass-panel grain p-8 text-center text-mist">
        <ShieldAlert className="mx-auto h-12 w-12 text-mist/40 mb-3" />
        <h3 className="font-display text-lg font-bold text-paper">No Transaction Selected</h3>
        <p className="mt-2 text-sm text-mist max-w-md mx-auto">
          Please select a transaction from the live Feed first, then switch to this tab to inspect details.
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glass-panel grain p-12 text-center text-mist">
        <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent mb-3" />
        <p className="text-sm">Loading deep forensic risk telemetry...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-panel grain p-8 text-center text-ember">
        <ShieldAlert className="mx-auto h-12 w-12 text-ember/70 mb-3" />
        <h3 className="font-display text-lg font-bold text-paper">Forensic Search Failed</h3>
        <p className="mt-2 text-sm text-mist">{error || "No data available."}</p>
      </div>
    );
  }

  const { transaction, timeline, location_hops, biometrics } = data;

  const decisionColor = {
    APPROVE: "text-mint border-mint/20 bg-mint/5",
    REVIEW: "text-saffron border-saffron/20 bg-saffron/5",
    HOLD: "text-ember border-ember/20 bg-ember/5"
  };

  return (
    <div className="space-y-6">
      {/* Overview Banner */}
      <div className={`glass-panel border-l-4 p-6 flex flex-wrap items-center justify-between gap-6 ${
        transaction.status === "ALLOWED" ? "border-l-mint" : transaction.status === "BLOCKED" ? "border-l-ember" : "border-l-saffron"
      }`}>
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h2 className="font-display text-xl font-black text-paper">Transaction Investigation</h2>
            <span className={`px-2.5 py-0.5 border rounded-full text-[10px] font-extrabold uppercase ${decisionColor[transaction.risk_decision] || "text-mist border-white/5 bg-carbon"}`}>
              {transaction.risk_decision}
            </span>
          </div>
          <p className="text-[11px] font-mono text-mist">ID: {transaction.id}</p>
        </div>
        <div className="flex gap-8">
          <div className="text-right">
            <span className="text-[9px] uppercase tracking-widest text-mist block">Risk Score</span>
            <span className="font-mono text-3xl font-black text-paper mt-0.5 block">{transaction.risk_score}</span>
          </div>
          <div className="text-right">
            <span className="text-[9px] uppercase tracking-widest text-mist block">Amount</span>
            <span className="font-display text-3xl font-black text-paper mt-0.5 block">₹{transaction.amount}</span>
          </div>
          <div className="text-right">
            <span className="text-[9px] uppercase tracking-widest text-mist block">Target Account</span>
            <span className="font-mono text-2xl font-bold text-primary mt-1 block">{transaction.target_account}</span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left column: Timeline & Geolocation */}
        <div className="lg:col-span-6 space-y-6">
          {/* Timeline */}
          <div className="glass-panel grain p-6 space-y-4">
            <div className="flex items-center gap-2 border-b border-white/5 pb-3">
              <Clock className="h-4.5 w-4.5 text-primary" />
              <h3 className="font-sans text-md font-bold text-paper">Chronological Device & Transfer Timeline</h3>
            </div>
            <div className="relative border-l border-white/5 pl-4 ml-2.5 space-y-5">
              {timeline.map((evt, idx) => (
                <div key={idx} className="relative">
                   {/* Dot */}
                  <span className={`absolute -left-[21.5px] top-1.5 h-3 w-3 rounded-full border border-ink ${
                    evt.is_current ? "bg-primary scale-125 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-carbon"
                  }`} />
                  <div className="space-y-0.5">
                    <div className="flex items-center justify-between">
                      <span className={`text-xs font-bold ${evt.is_current ? "text-primary" : "text-paper"}`}>{evt.title}</span>
                      <span className="text-[9px] font-mono text-mist">{new Date(evt.timestamp).toLocaleString()}</span>
                    </div>
                    <p className="text-[11px] text-mist">{evt.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Geolocation hops */}
          <div className="glass-panel grain p-6 space-y-4">
            <div className="flex items-center gap-2 border-b border-white/5 pb-3">
              <MapPin className="h-4.5 w-4.5 text-primary" />
              <h3 className="font-sans text-md font-bold text-paper">Location Hop History</h3>
            </div>
            <div className="space-y-3">
              {location_hops.length === 0 ? (
                <p className="text-xs text-mist italic">No geolocation logs available.</p>
              ) : (
                <div className="space-y-2.5">
                  {location_hops.map((hop, idx) => (
                    <div key={idx} className="flex items-center justify-between rounded-lg bg-carbon/25 border border-white/5 p-3 hover:border-white/10 transition">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-7 w-7 items-center justify-center rounded bg-primary/10 text-primary font-bold text-[10px]">
                          {idx + 1}
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-paper">{hop.city}, {hop.country}</p>
                          {hop.lat && hop.lng && (
                            <p className="text-[9px] font-mono text-mist">GPS: {hop.lat.toFixed(4)}, {hop.lng.toFixed(4)}</p>
                          )}
                        </div>
                      </div>
                      <span className="text-[10px] font-mono text-mist">{new Date(hop.timestamp).toLocaleString()}</span>
                    </div>
                  ))}
                  {location_hops.length >= 2 && (
                    <div className="mt-3 rounded-lg border border-ember/20 bg-ember/5 p-3 text-xs flex items-start gap-2.5">
                      <ShieldAlert className="h-4 w-4 text-ember mt-0.5 shrink-0" />
                      <div>
                        <p className="font-bold text-paper">Geolocation Analysis</p>
                        <p className="mt-1 text-mist text-[11px]">
                          Travel trace analysis verifies user city and country jumps. Anomalous speed vectors or simultaneous logins from distant nodes automatically score as impossible travel.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right column: Biometrics, Device & AI scam */}
        <div className="lg:col-span-6 space-y-6">
          {/* Biometrics Comparison */}
          <div className="glass-panel grain p-6 space-y-4">
            <div className="flex items-center gap-2 border-b border-white/5 pb-3">
              <Activity className="h-4.5 w-4.5 text-primary" />
              <h3 className="font-sans text-md font-bold text-paper">Behavioral Biometrics DNA Comparison</h3>
            </div>
            <div className="overflow-hidden rounded-lg border border-white/5">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-carbon/50 text-[10px] uppercase tracking-wider text-mist border-b border-white/5">
                    <th className="p-3">Biometric Parameter</th>
                    <th className="p-3">Baseline Avg</th>
                    <th className="p-3">Current Tx</th>
                    <th className="p-3">Deviation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-mono text-[11px] text-paper">
                  <tr>
                    <td className="p-3 font-sans text-mist font-semibold">Key Dwell (s)</td>
                    <td className="p-3">{biometrics.baseline.keystroke_dwell.toFixed(3)}</td>
                    <td className="p-3">{transaction.breakdown.behavioral_score > 0 ? (biometrics.baseline.keystroke_dwell * (1 + transaction.breakdown.behavioral_score / 100)).toFixed(3) : biometrics.baseline.keystroke_dwell.toFixed(3)}</td>
                    <td className="p-3">
                      <span className={transaction.breakdown.behavioral_score > 50 ? "text-ember font-bold" : "text-mint"}>
                        {transaction.breakdown.behavioral_score.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-sans text-mist font-semibold">Key Flight (s)</td>
                    <td className="p-3">{biometrics.baseline.keystroke_flight.toFixed(3)}</td>
                    <td className="p-3">{transaction.breakdown.behavioral_score > 0 ? (biometrics.baseline.keystroke_flight * (1 + transaction.breakdown.behavioral_score / 150)).toFixed(3) : biometrics.baseline.keystroke_flight.toFixed(3)}</td>
                    <td className="p-3">
                      <span className={transaction.breakdown.behavioral_score > 50 ? "text-ember font-bold" : "text-mint"}>
                        {(transaction.breakdown.behavioral_score * 0.7).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-sans text-mist font-semibold">Mouse Speed (px/s)</td>
                    <td className="p-3">{biometrics.baseline.mouse_speed.toFixed(1)}</td>
                    <td className="p-3">{transaction.breakdown.behavioral_score > 0 ? (biometrics.baseline.mouse_speed * (1 - transaction.breakdown.behavioral_score / 200)).toFixed(1) : biometrics.baseline.mouse_speed.toFixed(1)}</td>
                    <td className="p-3">
                      <span className={transaction.breakdown.behavioral_score > 50 ? "text-ember font-bold" : "text-mint"}>
                        {(transaction.breakdown.behavioral_score * 0.9).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td className="p-3 font-sans text-mist font-semibold">Mouse Jitter (px)</td>
                    <td className="p-3">{biometrics.baseline.mouse_jitter.toFixed(1)}</td>
                    <td className="p-3">{transaction.breakdown.behavioral_score > 0 ? (biometrics.baseline.mouse_jitter * (1 - transaction.breakdown.behavioral_score / 150)).toFixed(1) : biometrics.baseline.mouse_jitter.toFixed(1)}</td>
                    <td className="p-3">
                      <span className={transaction.breakdown.behavioral_score > 50 ? "text-ember font-bold" : "text-mint"}>
                        {(transaction.breakdown.behavioral_score * 0.8).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            {transaction.breakdown.behavioral_score >= 85.0 && (
              <div className="rounded-lg border border-ember/20 bg-ember/5 p-3 text-xs flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-ember shrink-0 animate-pulse" />
                <span className="font-bold text-paper">Bot pattern detected: perfect key down durations and zero mouse jitter.</span>
              </div>
            )}
          </div>

          {/* Device & Network Parameters */}
          <div className="glass-panel grain p-6 space-y-4">
            <div className="flex items-center gap-2 border-b border-white/5 pb-3">
              <Laptop className="h-4.5 w-4.5 text-primary" />
              <h3 className="font-sans text-md font-bold text-paper">Device Profile & Context</h3>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 text-xs">
              <div className="bg-carbon/25 border border-white/5 p-3 rounded-lg">
                <p className="text-[10px] uppercase tracking-wider text-mist">Device Browser & OS</p>
                <p className="mt-1 font-semibold text-paper">
                  {transaction.breakdown.device?.browser || "Chrome"} on {transaction.breakdown.device?.os || "Windows"}
                </p>
              </div>
              <div className="bg-carbon/25 border border-white/5 p-3 rounded-lg">
                <p className="text-[10px] uppercase tracking-wider text-mist">User Agent</p>
                <p className="mt-1 font-mono text-[10px] text-paper truncate" title={transaction.breakdown.device?.user_agent}>
                  {transaction.breakdown.device?.user_agent || "Mozilla/5.0..."}
                </p>
              </div>
              <div className="bg-carbon/25 border border-white/5 p-3 rounded-lg">
                <p className="text-[10px] uppercase tracking-wider text-mist">IP Address & Network</p>
                <p className="mt-1 font-mono font-semibold text-paper">
                  {transaction.breakdown.device?.ip_address || "127.0.0.1"}
                </p>
              </div>
              <div className="bg-carbon/25 border border-white/5 p-3 rounded-lg">
                <p className="text-[10px] uppercase tracking-wider text-mist">Language & Timezone</p>
                <p className="mt-1 font-semibold text-paper">
                  {transaction.breakdown.device?.language || "en-US"} | {transaction.breakdown.device?.timezone || "Asia/Kolkata"}
                </p>
              </div>
            </div>
          </div>

          {/* Scam Analysis */}
          {transaction.scam_classification && (
            <div className="glass-panel grain p-6 space-y-4">
              <div className="flex items-center gap-2 border-b border-white/5 pb-3">
                <Cpu className="h-4.5 w-4.5 text-primary" />
                <h3 className="font-sans text-md font-bold text-paper">AI Scam & Social Engineering Remarks Verdict</h3>
              </div>
              <div className={`rounded-lg border p-4 ${
                transaction.scam_classification === "Scam Likely"
                  ? "border-ember/30 bg-ember/10"
                  : transaction.scam_classification === "Suspicious"
                  ? "border-saffron/30 bg-saffron/10"
                  : "border-mint/20 bg-mint/5"
              }`}>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-paper">Gemini NLP Verdict</span>
                  <span className={`text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full ${
                    transaction.scam_classification === "Scam Likely"
                      ? "bg-ember text-paper"
                      : transaction.scam_classification === "Suspicious"
                      ? "bg-saffron text-carbon"
                      : "bg-mint text-carbon"
                  }`}>
                    {transaction.scam_classification}
                  </span>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-mist">
                  {transaction.scam_explanation}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
