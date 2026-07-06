import { useState } from "react";
import { Shield, Key, UserPlus, Loader2, AlertCircle, Activity, Cpu, Network, Globe, Radio } from "lucide-react";

export default function AuthScreen({ API_BASE, onLoginSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [form, setForm] = useState({ id: "", username: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const update = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value.trim() }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.id) {
      setError("User ID is required.");
      return;
    }
    if (!isLogin && !form.username) {
      setError("Username is required for registration.");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const endpoint = isLogin ? "/auth/login" : "/auth/register";
      const body = isLogin
        ? { id: form.id, username: "" }
        : { id: form.id, username: form.username, is_fraudster: false };

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        const user = await res.json();
        onLoginSuccess(user);
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || (isLogin ? "User ID not found. Register first." : "User ID already exists."));
      }
    } catch (e) {
      setError("Connection to PayShield server failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-12 min-h-[100dvh] bg-ink text-paper font-sans">
      {/* Left side: Premium Branding & System Status (Asymmetric Display) */}
      <div className="md:col-span-7 flex flex-col justify-between p-8 md:p-16 bg-gradient-to-br from-carbon to-ink border-r border-white/5 relative overflow-hidden">
        {/* Glow Effects */}
        <div className="absolute top-[-10%] left-[-10%] h-[400px] w-[400px] rounded-full bg-primary/5 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[10%] h-[500px] w-[500px] rounded-full bg-primary/3 blur-[150px]" />

        {/* Top Header */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-primary/30 bg-primary/10 text-primary shadow-glow-primary">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-primary font-bold">PRE-TRANSACTION SECURITY</span>
            <h2 className="text-lg font-bold tracking-tight text-paper mt-0.5">PayShield</h2>
          </div>
        </div>

        {/* Core Presentation Content */}
        <div className="my-auto py-12 relative z-10 max-w-xl">
          <h1 className="text-4xl md:text-5xl font-black tracking-tighter leading-none text-paper">
            Autonomous pre-auth payment risk mitigation.
          </h1>
          <p className="mt-4 text-sm text-mist leading-relaxed max-w-[50ch]">
            PayShield secures payment pipelines using supervised Random Forest classification models across behavioral, network, and graph intelligence vectors.
          </p>

          {/* Core Decision Engines Grid */}
          <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-2xl border border-white/5 bg-carbon/40 backdrop-blur-sm">
              <div className="flex items-center gap-2 text-primary">
                <Cpu className="h-4 w-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Behavioral DNA</span>
              </div>
              <p className="text-[11px] text-mist mt-1">keystroke dwell, flight, scroll & mouse jitter dynamics.</p>
            </div>
            
            <div className="p-4 rounded-2xl border border-white/5 bg-carbon/40 backdrop-blur-sm">
              <div className="flex items-center gap-2 text-primary">
                <Radio className="h-4 w-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Device Fingerprint</span>
              </div>
              <p className="text-[11px] text-mist mt-1">hardware entropy hashes, timezone & IP reputation lookup.</p>
            </div>

            <div className="p-4 rounded-2xl border border-white/5 bg-carbon/40 backdrop-blur-sm">
              <div className="flex items-center gap-2 text-primary">
                <Globe className="h-4 w-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Geovelocity Mesh</span>
              </div>
              <p className="text-[11px] text-mist mt-1">impossible travel speed limits & city/country transitions.</p>
            </div>

            <div className="p-4 rounded-2xl border border-white/5 bg-carbon/40 backdrop-blur-sm">
              <div className="flex items-center gap-2 text-primary">
                <Network className="h-4 w-4" />
                <span className="text-xs font-bold uppercase tracking-wider font-mono">Fraud Graph</span>
              </div>
              <p className="text-[11px] text-mist mt-1">circular routing, mule ring identification & shortest path link.</p>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="flex items-center gap-4 text-xs text-mist font-mono relative z-10">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
            Random Forest active
          </span>
          <span className="h-4 w-px bg-white/10" />
          <span>v1.2.0-secure</span>
        </div>
      </div>

      {/* Right side: Login & Register UI Form */}
      <div className="md:col-span-5 flex items-center justify-center p-8 bg-ink relative">
        <div className="w-full max-w-sm space-y-6">
          <div className="text-left">
            <h3 className="text-xl font-bold tracking-tight text-paper">
              {isLogin ? "Authenticate identity" : "Register telemetry baseline"}
            </h3>
            <p className="text-xs text-mist mt-1.5 leading-relaxed">
              {isLogin 
                ? "Enter your secure user identifier to login and load profile diagnostics." 
                : "Create a new profile. Your first transactions will seed the baseline telemetry."}
            </p>
          </div>

          {/* Form Card */}
          <div className="glass-panel grain p-6 border border-white/5 bg-carbon/25 backdrop-blur-md rounded-2xl">
            {/* Tab switch */}
            <div className="flex gap-2 border-b border-white/5 pb-4 mb-6">
              <button
                type="button"
                onClick={() => { setIsLogin(true); setError(null); }}
                className={`flex-1 py-1.5 text-center text-[10px] uppercase tracking-widest font-bold transition-all rounded-lg ${
                  isLogin ? "bg-primary/10 text-primary border border-primary/20" : "text-mist hover:text-paper"
                }`}
              >
                Login
              </button>
              <button
                type="button"
                onClick={() => { setIsLogin(false); setError(null); }}
                className={`flex-1 py-1.5 text-center text-[10px] uppercase tracking-widest font-bold transition-all rounded-lg ${
                  !isLogin ? "bg-primary/10 text-primary border border-primary/20" : "text-mist hover:text-paper"
                }`}
              >
                Register
              </button>
            </div>

            {error && (
              <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-ember/30 bg-ember/10 p-3.5 text-xs text-ember">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                <span className="leading-relaxed">{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-[9px] uppercase tracking-[0.2em] text-mist font-semibold mb-1.5">User Identifier</label>
                <input
                  type="text"
                  required
                  value={form.id}
                  onChange={update("id")}
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-paper placeholder-mist/40 outline-none transition-all duration-200 focus:border-primary/50 focus:ring-1 focus:ring-primary/20 font-mono"
                  placeholder="e.g. user_alice"
                />
              </div>

              {!isLogin && (
                <div>
                  <label className="block text-[9px] uppercase tracking-[0.2em] text-mist font-semibold mb-1.5">Full Name</label>
                  <input
                    type="text"
                    required
                    value={form.username}
                    onChange={update("username")}
                    className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-xs text-paper placeholder-mist/40 outline-none transition-all duration-200 focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
                    placeholder="e.g. Alice Chen"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2.5 rounded-xl border border-primary/45 bg-primary/10 px-6 py-3.5 mt-6 text-xs font-bold uppercase tracking-widest text-primary transition-all duration-300 hover:bg-primary hover:text-ink hover:shadow-glow-primary active:scale-[0.97] disabled:opacity-60 cursor-pointer"
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : isLogin ? (
                  <Key className="h-4 w-4" />
                ) : (
                  <UserPlus className="h-4 w-4" />
                )}
                {loading ? "Verifying..." : isLogin ? "Access Dashboard" : "Initiate Baseline"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
