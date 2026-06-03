import { useState } from "react";
import { ChevronDown, ChevronUp, Send, Loader2 } from "lucide-react";

const USERS = [
  "user_alice", "user_bob", "user_charlie", "user_diana", "user_eve",
  "user_frank", "user_grace", "user_henry", "user_iris", "user_jake",
];

const CHANNELS = ["UPI", "NEFT", "IMPS"];

const decisionBadge = {
  ALLOW:   "bg-mint/15 text-mint border-mint/40",
  BLOCK:   "bg-ember/15 text-ember border-ember/40",
  STEP_UP: "bg-gold/15 text-gold border-gold/40",
  DELAY:   "bg-lilac/15 text-lilac border-lilac/40",
};

const riskColor = (score) => {
  if (score >= 80) return "text-ember";
  if (score >= 50) return "text-gold";
  return "text-mint";
};

const inputClass =
  "w-full rounded-lg border border-white/10 bg-white/5 px-3.5 py-2.5 text-sm text-paper placeholder-mist/40 outline-none transition-all duration-200 focus:border-saffron/50 focus:ring-1 focus:ring-saffron/20 font-mono";

const labelClass =
  "block text-[10px] uppercase tracking-[0.2em] text-mist font-semibold mb-1.5";

export default function TransactionForm({ onSubmit, result }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    user_id: "user_alice",
    amount: 5000,
    target_account: "",
    channel: "UPI",
    location: "Chennai, IN",
    beneficiary_name: "",
  });

  const update = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onSubmit({
        ...form,
        amount: Number(form.amount),
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel grain shadow-xl transition-all duration-300 overflow-hidden">
      {/* ── Toggle Header ─────────────────────────────── */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-4 text-left transition-all duration-200 hover:bg-white/[0.02]"
      >
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg border border-saffron/30 bg-saffron/10 text-saffron text-xs font-bold">
            {open ? "−" : "+"}
          </span>
          <span className="font-display text-sm font-bold text-paper tracking-wide">
            Submit Manual Transaction
          </span>
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 text-mist transition-transform" />
        ) : (
          <ChevronDown className="h-4 w-4 text-mist transition-transform" />
        )}
      </button>

      {/* ── Collapsible Body ──────────────────────────── */}
      <div
        className={`transition-all duration-300 ease-in-out ${
          open ? "max-h-[800px] opacity-100" : "max-h-0 opacity-0"
        } overflow-hidden`}
      >
        <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-4">
          <div className="border-t border-white/5 pt-4" />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* User ID */}
            <div>
              <label className={labelClass}>User ID</label>
              <select value={form.user_id} onChange={update("user_id")} className={inputClass}>
                {USERS.map((u) => (
                  <option key={u} value={u} className="bg-ink text-paper">{u}</option>
                ))}
              </select>
            </div>

            {/* Amount */}
            <div>
              <label className={labelClass}>Amount (₹)</label>
              <input
                type="number"
                min={100}
                max={500000}
                value={form.amount}
                onChange={update("amount")}
                className={inputClass}
                placeholder="5000"
              />
            </div>

            {/* Target Account */}
            <div>
              <label className={labelClass}>Target Account</label>
              <input
                type="text"
                value={form.target_account}
                onChange={update("target_account")}
                className={inputClass}
                placeholder="ACC-XXXXX"
              />
            </div>

            {/* Channel */}
            <div>
              <label className={labelClass}>Channel</label>
              <select value={form.channel} onChange={update("channel")} className={inputClass}>
                {CHANNELS.map((c) => (
                  <option key={c} value={c} className="bg-ink text-paper">{c}</option>
                ))}
              </select>
            </div>

            {/* Location */}
            <div>
              <label className={labelClass}>Location</label>
              <input
                type="text"
                value={form.location}
                onChange={update("location")}
                className={inputClass}
                placeholder="Chennai, IN"
              />
            </div>

            {/* Beneficiary Name */}
            <div>
              <label className={labelClass}>Beneficiary Name <span className="text-mist/40">(optional)</span></label>
              <input
                type="text"
                value={form.beneficiary_name}
                onChange={update("beneficiary_name")}
                className={inputClass}
                placeholder="John Doe"
              />
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2.5 rounded-xl border border-saffron/45 bg-saffron/10 px-6 py-3 text-xs font-bold uppercase tracking-widest text-saffron transition-all duration-300 hover:bg-saffron hover:text-ink hover:shadow-glow-saffron active:scale-[0.97] disabled:opacity-60"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            {loading ? "Scoring..." : "Score Transaction"}
          </button>

          {/* ── Result Display ──────────────────────────── */}
          {result && (
            <div className="mt-4 rounded-xl border border-white/10 bg-carbon/50 p-5 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="flex flex-wrap items-center gap-3 mb-3">
                <span
                  className={`rounded-full border px-3.5 py-1 text-[10px] font-bold uppercase tracking-widest ${
                    decisionBadge[result.decision] || "text-paper border-white/20"
                  }`}
                >
                  {result.decision}
                </span>
                <span className={`font-mono text-lg font-bold ${riskColor(result.risk_score)}`}>
                  Score: {result.risk_score}
                </span>
              </div>
              {result.reason_codes && result.reason_codes.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {result.reason_codes.map((code, i) => (
                    <span
                      key={i}
                      className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[9px] font-mono text-mist uppercase tracking-wider"
                    >
                      {code}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
