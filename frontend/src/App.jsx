import { useCallback, useEffect, useMemo, useState } from "react";
import Header from "./components/Header.jsx";
import StatBar from "./components/StatBar.jsx";
import LiveFeed from "./components/LiveFeed.jsx";
import RiskScorePanel from "./components/RiskScorePanel.jsx";
import GraphVisualizer from "./components/GraphVisualizer.jsx";
import LiveMonitor from "./components/LiveMonitor.jsx";
import TransactionForm from "./components/TransactionForm.jsx";
import AlertFeed from "./components/AlertFeed.jsx";
import CaseManager from "./components/CaseManager.jsx";
import UserProfileModal from "./components/UserProfileModal.jsx";
import TerminalConsole from "./components/TerminalConsole.jsx";
import useSSE from "./hooks/useSSE.js";
import useGraphData from "./hooks/useGraphData.js";
import useDashboardStats from "./hooks/useDashboardStats.js";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001/api";

export default function App() {
  const [activeTab, setActiveTab] = useState("feed");
  const [transactions, setTransactions] = useState([]);
  const [selectedTx, setSelectedTx] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [cases, setCases] = useState([]);
  const [profile, setProfile] = useState(null);
  const [consoleLogs, setConsoleLogs] = useState([]);
  const [streamStatus, setStreamStatus] = useState({
    running: false,
    speed: 3.0,
    fraud_rate: 0.08,
    total_generated: 0,
    total_fraud_injected: 0,
    total_blocked: 0,
    total_allowed: 0,
    uptime_seconds: 0,
  });
  const [manualResult, setManualResult] = useState(null);

  const { status: serverStatus, lastEvent } = useSSE(API_BASE);
  const { graphData, refreshGraph } = useGraphData(API_BASE);
  const { stats, refreshStats } = useDashboardStats(API_BASE);

  const addConsoleLog = useCallback((type, message) => {
    const timestamp = new Date().toLocaleTimeString();
    setConsoleLogs((prev) => [...prev, { timestamp, type, message }].slice(-120));
  }, []);

  const refreshAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/history`);
      if (res.ok) {
        setAlerts(await res.json());
      }
    } catch (e) {
      addConsoleLog("SYSTEM_ERROR", "Unable to refresh alerts history.");
    }
  }, [addConsoleLog]);

  const refreshCases = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/cases`);
      if (res.ok) {
        setCases(await res.json());
      }
    } catch (e) {
      addConsoleLog("SYSTEM_ERROR", "Unable to refresh fraud cases.");
    }
  }, [addConsoleLog]);

  const loadProfile = useCallback(
    async (userId) => {
      if (!userId) return;
      try {
        const res = await fetch(`${API_BASE}/user/${userId}/profile`);
        if (res.ok) {
          setProfile(await res.json());
        }
      } catch (e) {
        addConsoleLog("SYSTEM_ERROR", "Unable to fetch user profile.");
      }
    },
    [addConsoleLog]
  );

  /* ── Stream control functions ──────────────────────────── */

  const fetchStreamStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/stream/status`);
      if (res.ok) setStreamStatus(await res.json());
    } catch (e) { /* silent */ }
  }, []);

  const startStream = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/stream/start`, { method: 'POST' });
      addConsoleLog('SYSTEM_INFO', 'Live transaction stream started.');
      fetchStreamStatus();
    } catch (e) {
      addConsoleLog('SYSTEM_ERROR', 'Failed to start stream.');
    }
  }, [addConsoleLog, fetchStreamStatus]);

  const stopStream = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/stream/stop`, { method: 'POST' });
      addConsoleLog('SYSTEM_INFO', 'Live transaction stream stopped.');
      fetchStreamStatus();
    } catch (e) {
      addConsoleLog('SYSTEM_ERROR', 'Failed to stop stream.');
    }
  }, [addConsoleLog, fetchStreamStatus]);

  const updateStreamConfig = useCallback(async (config) => {
    try {
      await fetch(`${API_BASE}/stream/config`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      fetchStreamStatus();
    } catch (e) { /* silent */ }
  }, [fetchStreamStatus]);

  const submitManualTransaction = useCallback(async (formData) => {
    try {
      const res = await fetch(`${API_BASE}/transaction/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        const data = await res.json();
        setManualResult(data);
        addConsoleLog('SYSTEM_INFO', `Manual: [${data.decision}] ₹${formData.amount} scored ${data.risk_score}`);
        return data;
      }
    } catch (e) {
      addConsoleLog('SYSTEM_ERROR', 'Manual transaction submission failed.');
    }
    return null;
  }, [addConsoleLog]);

  /* ── Case management ───────────────────────────────────── */

  const updateCase = useCallback(
    async (caseId, outcome) => {
      try {
        const res = await fetch(`${API_BASE}/cases/${caseId}?outcome=${outcome}`, {
          method: "PATCH",
        });
        if (res.ok) {
          refreshCases();
        }
      } catch (e) {
        addConsoleLog("SYSTEM_ERROR", "Case update failed.");
      }
    },
    [addConsoleLog, refreshCases]
  );

  /* ── Initial load ──────────────────────────────────────── */
  useEffect(() => {
    fetchStreamStatus();
    refreshAlerts();
    refreshCases();
  }, [fetchStreamStatus, refreshAlerts, refreshCases]);

  /* ── Poll stream status every 3s ───────────────────────── */
  useEffect(() => {
    const interval = setInterval(fetchStreamStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchStreamStatus]);

  /* ── SSE event handler ─────────────────────────────────── */
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === "CONNECTED") {
      addConsoleLog("SYSTEM_INFO", lastEvent.message);
      return;
    }
    if (lastEvent.type === "TRANSACTION_SCORED") {
      const tx = lastEvent.data;
      setTransactions((prev) => [tx, ...prev].slice(0, 50));
      setSelectedTx(tx);
      addConsoleLog(
        tx.decision === "BLOCK" ? "ALERT_CRITICAL" : tx.decision === "DELAY" ? "ALERT_HIGH" : "TRANSACTION_SCORED",
        `[${tx.decision}] ₹${tx.amount} to ${tx.target_account} scored ${tx.risk_score}`
      );
      refreshGraph();
      refreshStats();
      refreshAlerts();
      refreshCases();
      loadProfile(tx.user_id);
    }
  }, [addConsoleLog, lastEvent, loadProfile, refreshAlerts, refreshCases, refreshGraph, refreshStats]);

  useEffect(() => {
    if (activeTab === "profile") {
      const userId = selectedTx?.user_id || "user_alice";
      loadProfile(userId);
    }
  }, [activeTab, loadProfile, selectedTx]);

  const selectedId = useMemo(() => selectedTx?.transaction_id, [selectedTx]);

  return (
    <div className="min-h-screen bg-ink text-paper">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        serverStatus={serverStatus}
        streamStatus={streamStatus}
        onToggleStream={streamStatus.running ? stopStream : startStream}
      />

      <main className="mx-auto w-full max-w-7xl px-6 py-8">
        {activeTab === "feed" && (
          <div className="space-y-6">
            <StatBar stats={stats} />
            <LiveMonitor
              streamStatus={streamStatus}
              onStartStream={startStream}
              onStopStream={stopStream}
              onUpdateConfig={updateStreamConfig}
            />
            <TransactionForm onSubmit={submitManualTransaction} result={manualResult} />
            <div className="grid gap-6 lg:grid-cols-12">
              <div className="lg:col-span-7 space-y-6">
                <LiveFeed transactions={transactions} selectedId={selectedId} onSelect={setSelectedTx} />
                <AlertFeed alerts={alerts} />
              </div>
              <div className="lg:col-span-5 space-y-6">
                <RiskScorePanel transaction={selectedTx} />
                <TerminalConsole logs={consoleLogs} />
              </div>
            </div>
          </div>
        )}

        {activeTab === "profile" && (
          <div className="space-y-6">
            <UserProfileModal profile={profile} />
            <RiskScorePanel transaction={selectedTx} />
          </div>
        )}

        {activeTab === "graph" && (
          <div className="glass-panel grain p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-bold text-paper">Fraud Network Graph</h2>
              <span className="data-pill">D3 Force Layout</span>
            </div>
            <div className="mt-4">
              <GraphVisualizer nodes={graphData.nodes} edges={graphData.edges} />
            </div>
          </div>
        )}

        {activeTab === "cases" && (
          <CaseManager cases={cases} onUpdateCase={updateCase} />
        )}

        {activeTab === "stats" && (
          <div className="space-y-6">
            <StatBar stats={stats} />
            <div className="grid gap-4 md:grid-cols-3">
              <div className="glass-panel grain p-5">
                <p className="text-xs uppercase tracking-[0.2em] text-mist">False Positive Rate</p>
                <p className="mt-3 font-display text-3xl font-bold text-paper">{stats.false_positive_rate}%</p>
              </div>
              <div className="glass-panel grain p-5">
                <p className="text-xs uppercase tracking-[0.2em] text-mist">Cases Under Review</p>
                <p className="mt-3 font-display text-3xl font-bold text-paper">{cases.length}</p>
              </div>
              <div className="glass-panel grain p-5">
                <p className="text-xs uppercase tracking-[0.2em] text-mist">Latest Decision</p>
                <p className="mt-3 font-display text-2xl font-bold text-paper">
                  {selectedTx ? selectedTx.decision : "—"}
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
