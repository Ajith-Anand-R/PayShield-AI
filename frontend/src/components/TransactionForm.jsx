import { useState, useEffect, useRef } from "react";
import { ChevronDown, ChevronUp, Send, Loader2 } from "lucide-react";

const CHANNELS = ["UPI", "NEFT", "IMPS"];

const decisionBadge = {
  ALLOW:   "bg-mint/15 text-mint border-mint/40",
  BLOCK:   "bg-ember/15 text-ember border-ember/40",
  STEP_UP: "bg-gold/15 text-gold border-gold/40",
  REVIEW:  "bg-lilac/15 text-lilac border-lilac/40",
};

const riskColor = (score) => {
  if (score >= 80) return "text-ember";
  if (score >= 50) return "text-gold";
  return "text-mint";
};

const inputClass =
  "w-full rounded-lg border border-white/10 bg-white/5 px-3.5 py-2.5 text-sm text-paper placeholder-mist/40 outline-none transition-all duration-200 focus:border-primary/50 focus:ring-1 focus:ring-primary/20 font-mono";

const labelClass =
  "block text-[10px] uppercase tracking-[0.2em] text-mist font-semibold mb-1.5";

export default function TransactionForm({ onSubmit, result, currentUser }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    user_id: currentUser?.id || "",
    amount: 5000,
    target_account: "",
    channel: "UPI",
    location: "Chennai, IN",
    beneficiary_name: "",
    remarks: "",
  });

  const [deviceDetails, setDeviceDetails] = useState({
    device_hash: "unknown_device",
    browser: "Chrome",
    os: "Windows",
    ip_address: "127.0.0.1",
    location: "Chennai, IN",
    screen_resolution: `${window.screen.width}x${window.screen.height}`,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
    user_agent: navigator.userAgent,
    latitude: null,
    longitude: null,
    city: "Chennai",
    region: "Tamil Nadu",
    country: "IN",
  });

  // Telemetry refs for keystroke/mouse/scroll profiling
  const keystrokeDwells = useRef([]);
  const keystrokeFlights = useRef([]);
  const keydownTimes = useRef({});
  const lastKeyupTime = useRef(null);

  const mouseSpeeds = useRef([]);
  const mouseJitters = useRef([]);
  const lastMousePos = useRef({ x: null, y: null, time: null });
  const lastJitterPos = useRef(null);

  const scrollVelocities = useRef([]);
  const lastScrollTime = useRef(null);
  const lastScrollTop = useRef(0);

  const [telemetryCounts, setTelemetryCounts] = useState({ keys: 0, mouse: 0, scroll: 0 });

  // 1. Initialize FingerprintJS
  useEffect(() => {
    const initFingerprint = async () => {
      try {
        const fpPromise = await import("@fingerprintjs/fingerprintjs");
        const fp = await fpPromise.default.load();
        const fpResult = await fp.get();
        
        const ua = navigator.userAgent;
        let browser = "Chrome";
        let os = "Windows";
        if (ua.indexOf("Firefox") > -1) browser = "Firefox";
        else if (ua.indexOf("Safari") > -1 && ua.indexOf("Chrome") === -1) browser = "Safari";
        else if (ua.indexOf("Edge") > -1) browser = "Edge";
        
        if (ua.indexOf("Mac") > -1) os = "macOS";
        else if (ua.indexOf("Linux") > -1) os = "Linux";
        else if (ua.indexOf("Android") > -1) os = "Android";
        else if (ua.indexOf("iPhone") > -1 || ua.indexOf("iPad") > -1) os = "iOS";

        setDeviceDetails((prev) => ({
          ...prev,
          device_hash: fpResult.visitorId,
          browser,
          os,
        }));
      } catch (e) {
        console.error("Failed to load FingerprintJS:", e);
      }
    };
    initFingerprint();
  }, []);

  // 2. Fetch Geolocation/IP Data
  useEffect(() => {
    const fetchGeoIP = async () => {
      try {
        const res = await fetch("https://ipapi.co/json/");
        if (res.ok) {
          const data = await res.json();
          const locationStr = `${data.city || "Chennai"}, ${data.country_code || "IN"}`;
          setDeviceDetails((prev) => ({
            ...prev,
            ip_address: data.ip || prev.ip_address,
            location: locationStr,
            city: data.city || "Chennai",
            region: data.region || "Tamil Nadu",
            country: data.country_code || "IN",
            latitude: data.latitude || null,
            longitude: data.longitude || null,
          }));
          setForm((prev) => ({
            ...prev,
            location: locationStr,
          }));
        }
      } catch (e) {
        console.error("Failed to fetch GeoIP:", e);
      }
    };
    fetchGeoIP();
  }, []);

  // 3. Browser Geolocation fallback
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          setDeviceDetails((prev) => ({
            ...prev,
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          }));
        },
        (err) => {
          console.warn("High precision browser geolocation rejected:", err);
        }
      );
    }
  }, []);

  // 4. Mouse and Scroll Telemetry Listeners
  useEffect(() => {
    const handleMouseMove = (e) => {
      const now = performance.now();
      const x = e.clientX;
      const y = e.clientY;
      
      if (lastMousePos.current.x !== null) {
        const dx = x - lastMousePos.current.x;
        const dy = y - lastMousePos.current.y;
        const dt = now - lastMousePos.current.time;
        
        if (dt > 0) {
          const dist = Math.sqrt(dx * dx + dy * dy);
          const speed = (dist / dt) * 100.0; // scale speeds
          if (speed < 1000.0) {
            mouseSpeeds.current.push(speed);
          }
          
          if (lastJitterPos.current) {
            const prevDx = lastMousePos.current.x - lastJitterPos.current.x;
            const prevDy = lastMousePos.current.y - lastJitterPos.current.y;
            const angle1 = Math.atan2(dy, dx);
            const angle2 = Math.atan2(prevDy, prevDx);
            const jitter = Math.abs(angle1 - angle2) * 10.0;
            mouseJitters.current.push(jitter);
          }
          lastJitterPos.current = { x: lastMousePos.current.x, y: lastMousePos.current.y };
          
          if (mouseSpeeds.current.length % 5 === 0) {
            setTelemetryCounts((prev) => ({ ...prev, mouse: mouseSpeeds.current.length }));
          }
        }
      }
      lastMousePos.current = { x, y, time: now };
    };

    const handleScroll = () => {
      const now = performance.now();
      const st = window.pageYOffset || document.documentElement.scrollTop;
      if (lastScrollTime.current !== null) {
        const dt = now - lastScrollTime.current;
        const dy = Math.abs(st - lastScrollTop.current);
        if (dt > 0) {
          const vel = (dy / dt) * 100.0;
          scrollVelocities.current.push(vel);
          setTelemetryCounts((prev) => ({ ...prev, scroll: scrollVelocities.current.length }));
        }
      }
      lastScrollTime.current = now;
      lastScrollTop.current = st;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("scroll", handleScroll);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // 5. Keystroke Dynamics Listeners
  const handleKeyDown = (e) => {
    const now = performance.now();
    const key = e.key;
    if (keydownTimes.current[key]) return;
    keydownTimes.current[key] = now;
    
    if (lastKeyupTime.current) {
      const flight = (now - lastKeyupTime.current) / 1000.0;
      if (flight < 2.0) {
        keystrokeFlights.current.push(flight);
        setTelemetryCounts((prev) => ({ ...prev, keys: keystrokeDwells.current.length + keystrokeFlights.current.length }));
      }
    }
  };

  const handleKeyUp = (e) => {
    const now = performance.now();
    const key = e.key;
    if (keydownTimes.current[key]) {
      const dwell = (now - keydownTimes.current[key]) / 1000.0;
      if (dwell < 1.0) {
        keystrokeDwells.current.push(dwell);
        setTelemetryCounts((prev) => ({ ...prev, keys: keystrokeDwells.current.length + keystrokeFlights.current.length }));
      }
      delete keydownTimes.current[key];
    }
    lastKeyupTime.current = now;
  };

  useEffect(() => {
    if (currentUser?.id) {
      setForm((prev) => ({ ...prev, user_id: currentUser.id }));
    }
  }, [currentUser]);

  const update = (field) => (e) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const average = (arr, fallback) => {
    if (!arr || arr.length === 0) return fallback;
    const sum = arr.reduce((a, b) => a + b, 0);
    return sum / arr.length;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const dwell = average(keystrokeDwells.current, 0.10);
      const flight = average(keystrokeFlights.current, 0.15);
      const speed = average(mouseSpeeds.current, 250.0);
      const jitter = average(mouseJitters.current, 12.0);
      const scroll = average(scrollVelocities.current, 80.0);

      // Package full transaction telemetry payload
      const telemetryPayload = {
        user_id: form.user_id,
        amount: Number(form.amount),
        currency: "INR",
        channel: form.channel,
        target_account: form.target_account,
        beneficiary_name: form.beneficiary_name || "Unknown Beneficiary",
        beneficiary_ifsc: "IOB0000123", // mock/default IFSC for hackathon
        remarks: form.remarks || "",
        device: {
          ...deviceDetails,
          location: form.location, // allow UI override
        },
        behavior: {
          keystroke_dwell: dwell,
          keystroke_flight: flight,
          mouse_speed: speed,
          mouse_jitter: jitter,
          scroll_velocity: scroll,
        }
      };

      await onSubmit(telemetryPayload);
      
      // Reset telemetry counts on submission
      keystrokeDwells.current = [];
      keystrokeFlights.current = [];
      mouseSpeeds.current = [];
      mouseJitters.current = [];
      scrollVelocities.current = [];
      setTelemetryCounts({ keys: 0, mouse: 0, scroll: 0 });
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
          <span className="flex h-6 w-6 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary text-xs font-bold">
            {open ? "−" : "+"}
          </span>
          <span className="font-sans text-sm font-bold text-paper tracking-wide">
            Submit Manual Transaction (With Live Biometrics)
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
          open ? "max-h-[900px] opacity-100" : "max-h-0 opacity-0"
        } overflow-hidden`}
      >
        <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-4">
          <div className="border-t border-white/5 pt-4" />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* User ID */}
            <div>
              <label className={labelClass}>User ID</label>
              <input
                type="text"
                disabled
                value={currentUser ? `${currentUser.username} (${currentUser.id})` : ""}
                className={`${inputClass} opacity-60 cursor-not-allowed`}
              />
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
                onKeyDown={handleKeyDown}
                onKeyUp={handleKeyUp}
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
                onKeyDown={handleKeyDown}
                onKeyUp={handleKeyUp}
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
              <label className={labelClass}>Location (Simulated or Real)</label>
              <input
                type="text"
                value={form.location}
                onChange={update("location")}
                onKeyDown={handleKeyDown}
                onKeyUp={handleKeyUp}
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
                onKeyDown={handleKeyDown}
                onKeyUp={handleKeyUp}
                className={inputClass}
                placeholder="John Doe"
              />
            </div>

            {/* Remarks / Purpose */}
            <div>
              <label className={labelClass}>Remarks / Purpose <span className="text-mist/40">(tested by Gemini Scam NLP)</span></label>
              <input
                type="text"
                value={form.remarks}
                onChange={update("remarks")}
                onKeyDown={handleKeyDown}
                onKeyUp={handleKeyUp}
                className={inputClass}
                placeholder="e.g. part time job commission"
              />
            </div>
          </div>

          {/* Live Telemetry Ticker */}
          <div className="flex flex-wrap items-center gap-4 bg-white/5 border border-white/5 px-4 py-2.5 rounded-xl text-xs text-mist font-mono">
            <span className="flex h-2 w-2 rounded-full bg-primary animate-pulse" />
            <span className="font-bold text-primary">Live Biometrics DNA Ticker:</span>
            <span>⌨️ {telemetryCounts.keys} keystroke events</span>
            <span>🖱️ {telemetryCounts.mouse} mouse moves</span>
            <span>📜 {telemetryCounts.scroll} scroll velocities</span>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading}
            className="flex items-center gap-2.5 rounded-xl border border-primary/45 bg-primary/10 px-6 py-3 text-xs font-bold uppercase tracking-widest text-primary transition-all duration-300 hover:bg-primary hover:text-ink hover:shadow-glow-primary active:scale-[0.97] disabled:opacity-60 cursor-pointer"
          >
            {loading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            {loading ? "Scoring with Biometrics..." : "Score Transaction"}
          </button>

          {/* ── Result Display ──────────────────────────── */}
          {result && (
            <div className="mt-4 rounded-xl border border-white/10 bg-carbon/50 p-5 animate-in fade-in slide-in-from-bottom-2 duration-300">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-3">
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
                {result.decision === "BLOCK" && (
                  <span className="text-[10px] text-ember font-bold bg-ember/10 px-2.5 py-1 rounded-full border border-ember/25">
                    BLOCKED BY PAYSHIELD
                  </span>
                )}
                {result.decision === "ALLOW" && (
                  <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${
                    result.payment_success || result.payment_id
                      ? "text-mint bg-mint/10 border-mint/25"
                      : "text-saffron bg-saffron/10 border-saffron/25 animate-pulse"
                  }`}>
                    {result.payment_success || result.payment_id ? "PAYMENT SUCCESS" : "PAYMENT PENDING"}
                  </span>
                )}
              </div>
              
              {result.decision === "BLOCK" ? (
                <div className="mt-3 rounded-lg border border-ember/30 bg-ember/5 p-3.5 flex items-center gap-3 text-xs text-ember">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ember text-ink text-[10px] font-extrabold">!</span>
                  <div>
                    <p className="font-bold">Transaction Intercepted Before Authorization</p>
                    <p className="opacity-80 mt-0.5">Threat score exceeded safety threshold. Funds never left the source account.</p>
                  </div>
                </div>
              ) : (
                <div className="mt-3 text-xs text-mist space-y-2">
                  <p>PayShield pre-authorization evaluation: <span className="text-mint font-bold">{result.decision}</span>.</p>
                  {result.payment_success || result.payment_id ? (
                    <div className="rounded-lg border border-mint/30 bg-mint/5 p-3 text-mint font-mono text-[11px] flex flex-col gap-0.5">
                      <div className="flex justify-between">
                        <span>Gateway:</span>
                        <span>Razorpay Test Mode</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Payment ID:</span>
                        <span>{result.payment_id || "pay_mock_success"}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Status:</span>
                        <span className="font-bold text-mint">CAPTURED (PAID)</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-saffron italic">Secure Checkout window triggered. Complete payment to finalize...</p>
                  )}
                </div>
              )}
              
              {result.reason_codes && result.reason_codes.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-white/5">
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
