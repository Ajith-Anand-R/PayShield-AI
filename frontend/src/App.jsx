import { useCallback, useEffect, useMemo, useState } from "react";
import Header from "./components/Header.jsx";
import StatBar from "./components/StatBar.jsx";
import LiveFeed from "./components/LiveFeed.jsx";
import RiskScorePanel from "./components/RiskScorePanel.jsx";
import GraphVisualizer from "./components/GraphVisualizer.jsx";
import TransactionForm from "./components/TransactionForm.jsx";
import AlertFeed from "./components/AlertFeed.jsx";
import CaseManager from "./components/CaseManager.jsx";
import UserProfileModal from "./components/UserProfileModal.jsx";
import TerminalConsole from "./components/TerminalConsole.jsx";
import AuthScreen from "./components/AuthScreen.jsx";
import InvestigationConsole from "./components/InvestigationConsole.jsx";
import useSSE from "./hooks/useSSE.js";
import useGraphData from "./hooks/useGraphData.js";
import useDashboardStats from "./hooks/useDashboardStats.js";
import RazorpayModal from "./components/RazorpayModal.jsx";
import DiagnosticsPanel from "./components/DiagnosticsPanel.jsx";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8001/api";

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => {
    const saved = localStorage.getItem("payshield_user");
    return saved ? JSON.parse(saved) : null;
  });
  const [activeTab, setActiveTab] = useState("feed");
  const [transactions, setTransactions] = useState([]);
  const [selectedTx, setSelectedTx] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [cases, setCases] = useState([]);
  const [profile, setProfile] = useState(null);
  const [consoleLogs, setConsoleLogs] = useState([]);
  const [manualResult, setManualResult] = useState(null);
  const [sandboxPayment, setSandboxPayment] = useState(null);

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

  const handleLoginSuccess = useCallback((user) => {
    setCurrentUser(user);
    localStorage.setItem("payshield_user", JSON.stringify(user));
    addConsoleLog("SYSTEM_INFO", `Logged in as ${user.username} (${user.id}).`);
  }, [addConsoleLog]);

  const handleLogout = useCallback(() => {
    setCurrentUser(null);
    localStorage.removeItem("payshield_user");
    addConsoleLog("SYSTEM_INFO", "Logged out successfully.");
  }, [addConsoleLog]);

  const submitManualTransaction = useCallback(async (formData) => {
    try {
      const res = await fetch(`${API_BASE}/transaction/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      if (res.ok) {
        const data = await res.json();
        setManualResult(data);
        addConsoleLog('SYSTEM_INFO', `Transaction: [${data.decision}] ₹${formData.amount} scored ${data.risk_score}`);
        
        // If decision is BLOCK, intercept payment and do not proceed
        if (data.decision === "BLOCK") {
          addConsoleLog('ALERT_CRITICAL', `PayShield Pre-Auth: BLOCKED transaction ₹${formData.amount} to prevent potential fraud.`);
          return data;
        }
        
        // If approved/reviewed, call Razorpay order creation
        addConsoleLog('SYSTEM_INFO', 'Initiating Razorpay gateway integration...');
        try {
          const orderRes = await fetch(`${API_BASE}/razorpay/order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              transaction_id: data.transaction_id,
              amount: Number(formData.amount)
            })
          });
          if (orderRes.ok) {
            const orderData = await orderRes.json();
            const isRealKey = orderData.key_id && 
                              orderData.key_id !== "rzp_test_placeholder_key" && 
                              !orderData.key_id.includes("placeholder");
            
            if (isRealKey) {
              addConsoleLog('SYSTEM_INFO', `Opening Razorpay Checkout widget (Order ID: ${orderData.order_id})...`);
              const loadScript = () => {
                return new Promise((resolve) => {
                  if (window.Razorpay) { resolve(true); return; }
                  const script = document.createElement("script");
                  script.src = "https://checkout.razorpay.com/v1/checkout.js";
                  script.onload = () => resolve(true);
                  script.onerror = () => resolve(false);
                  document.body.appendChild(script);
                });
              };
              
              const scriptLoaded = await loadScript();
              if (scriptLoaded && window.Razorpay) {
                const options = {
                  key: orderData.key_id,
                  amount: orderData.amount * 100,
                  currency: orderData.currency,
                  name: "PayShield Gateway",
                  description: `Pre-Auth Secured (Score: ${data.risk_score})`,
                  order_id: orderData.order_id.startsWith("order_mock") ? undefined : orderData.order_id,
                  handler: async function (response) {
                    addConsoleLog('SYSTEM_INFO', `Razorpay Payment Succeeded. Payment ID: ${response.razorpay_payment_id}`);
                    try {
                      const successRes = await fetch(`${API_BASE}/razorpay/success`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          transaction_id: data.transaction_id,
                          razorpay_payment_id: response.razorpay_payment_id,
                          razorpay_order_id: response.razorpay_order_id || orderData.order_id,
                          razorpay_signature: response.razorpay_signature || "signature_mock"
                        })
                      });
                      if (successRes.ok) {
                        setManualResult(prev => ({
                          ...prev,
                          payment_success: true,
                          payment_id: response.razorpay_payment_id
                        }));
                        addConsoleLog('SYSTEM_INFO', 'Payment successfully verified and settled.');
                      }
                    } catch (e) {
                      addConsoleLog('SYSTEM_ERROR', 'Payment callback registration failed.');
                    }
                  },
                  prefill: {
                    name: currentUser ? currentUser.username : "Alice Chen",
                    email: `${formData.user_id}@payshield.internal`
                  },
                  theme: {
                    color: "#FF9F1C"
                  }
                };
                const rzp = new window.Razorpay(options);
                rzp.open();
              } else {
                addConsoleLog('SYSTEM_ERROR', 'Could not load Razorpay JS SDK. Simulating checkout instead.');
                setSandboxPayment({
                  transaction_id: data.transaction_id,
                  amount: formData.amount,
                  order_id: orderData.order_id,
                  key_id: orderData.key_id,
                  beneficiary_name: formData.beneficiary_name || "Merchant/Beneficiary"
                });
              }
            } else {
              // Open Simulated Sandbox Checkout Modal
              setSandboxPayment({
                transaction_id: data.transaction_id,
                amount: formData.amount,
                order_id: orderData.order_id,
                key_id: orderData.key_id,
                beneficiary_name: formData.beneficiary_name || "Merchant/Beneficiary"
              });
            }
          } else {
            addConsoleLog('SYSTEM_ERROR', 'Failed to generate Razorpay order from backend.');
          }
        } catch (e) {
          addConsoleLog('SYSTEM_ERROR', 'Razorpay integration error.');
        }
        
        return data;
      } else {
        const err = await res.json().catch(() => ({}));
        addConsoleLog('SYSTEM_ERROR', err.detail || 'Transaction submission rejected.');
      }
    } catch (e) {
      addConsoleLog('SYSTEM_ERROR', 'Manual transaction submission failed.');
    }
    return null;
  }, [addConsoleLog, currentUser]);

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

  const handlePaymentSuccess = useCallback((payId) => {
    setManualResult(prev => ({
      ...prev,
      payment_success: true,
      payment_id: payId
    }));
    addConsoleLog('SYSTEM_INFO', `Simulated Payment success: ${payId}`);
    setSandboxPayment(null);
  }, [addConsoleLog]);

  const handlePaymentFailure = useCallback(() => {
    addConsoleLog('SYSTEM_INFO', 'Simulated Razorpay Payment failed/cancelled.');
    setSandboxPayment(null);
  }, [addConsoleLog]);


  /* ── Initial load ──────────────────────────────────────── */
  useEffect(() => {
    if (currentUser) {
      refreshAlerts();
      refreshCases();
    }
  }, [currentUser, refreshAlerts, refreshCases]);

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
        tx.decision === "HOLD" ? "ALERT_CRITICAL" : tx.decision === "REVIEW" ? "ALERT_HIGH" : "TRANSACTION_SCORED",
        `[${tx.decision}] ₹${tx.amount} to ${tx.target_account} scored ${tx.risk_score}`
      );
      refreshGraph();
      refreshStats();
      refreshAlerts();
      refreshCases();
      if (currentUser && tx.user_id === currentUser.id) {
        loadProfile(tx.user_id);
      }
    }
  }, [addConsoleLog, lastEvent, loadProfile, refreshAlerts, refreshCases, refreshGraph, refreshStats, currentUser]);

  useEffect(() => {
    if (activeTab === "profile" && currentUser) {
      loadProfile(currentUser.id);
    }
  }, [activeTab, loadProfile, currentUser]);

  const selectedId = useMemo(() => selectedTx?.transaction_id, [selectedTx]);

  if (!currentUser) {
    return (
      <AuthScreen
        API_BASE={API_BASE}
        onLoginSuccess={handleLoginSuccess}
      />
    );
  }

  return (
    <div className="min-h-[100dvh] bg-ink text-paper">
      <Header
        activeTab={activeTab}
        onTabChange={setActiveTab}
        serverStatus={serverStatus}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      <main className="mx-auto w-full max-w-7xl px-6 py-8">
        {activeTab === "feed" && (
          <div className="space-y-6">
            <StatBar stats={stats} />
            <TransactionForm
              onSubmit={submitManualTransaction}
              result={manualResult}
              currentUser={currentUser}
            />
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

        {activeTab === "investigation" && (
          <InvestigationConsole transactionId={selectedTx?.transaction_id} apiBase={API_BASE} />
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
              <h2 className="font-sans text-lg font-bold text-paper">Fraud Network Graph</h2>
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
          <DiagnosticsPanel apiBase={API_BASE} />
        )}
      </main>

      {/* simulated Razorpay Sandbox payment modal */}
      {sandboxPayment && (
        <RazorpayModal
          sandboxPayment={sandboxPayment}
          manualResult={manualResult}
          currentUser={currentUser}
          apiBase={API_BASE}
          onPaymentSuccess={handlePaymentSuccess}
          onPaymentFailure={handlePaymentFailure}
        />
      )}
    </div>
  );
}
