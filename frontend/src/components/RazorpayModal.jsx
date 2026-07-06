import { useState, useEffect } from "react";

export default function RazorpayModal({
  sandboxPayment,
  manualResult,
  currentUser,
  apiBase,
  onPaymentSuccess,
  onPaymentFailure
}) {
  const [razorpayTab, setRazorpayTab] = useState("card"); // "card", "upi", "netbanking"
  const [otpCode, setOtpCode] = useState("");
  const [paymentState, setPaymentState] = useState("idle"); // "idle", "processing", "otp", "success", "failed"
  const [otpError, setOtpError] = useState("");
  const [upiId, setUpiId] = useState("");
  const [qrCodeOption, setQrCodeOption] = useState(false);
  const [qrTimer, setQrTimer] = useState(300);
  const [cardDetails, setCardDetails] = useState({
    number: "",
    expiry: "",
    cvv: "",
    name: ""
  });

  useEffect(() => {
    let interval;
    if (qrCodeOption && qrTimer > 0) {
      interval = setInterval(() => {
        setQrTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [qrCodeOption, qrTimer]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleSimulateSuccess = async () => {
    const payId = `pay_mock_${Math.random().toString(36).substr(2, 9)}`;
    const orderId = sandboxPayment.order_id || `order_mock_${Math.random().toString(36).substr(2, 9)}`;
    
    try {
      const successRes = await fetch(`${apiBase}/razorpay/success`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          transaction_id: sandboxPayment.transaction_id,
          razorpay_payment_id: payId,
          razorpay_order_id: orderId,
          razorpay_signature: "simulated_signature_value"
        })
      });
      if (successRes.ok) {
        onPaymentSuccess(payId);
      } else {
        setPaymentState("failed");
        setTimeout(() => {
          onPaymentFailure();
        }, 1500);
      }
    } catch (e) {
      setPaymentState("failed");
      setTimeout(() => {
        onPaymentFailure();
      }, 1500);
    }
  };

  const handleSimulateFailure = () => {
    setPaymentState("failed");
    setTimeout(() => {
      onPaymentFailure();
    }, 1500);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#f9fafb] text-[#1e293b] max-w-[420px] w-full rounded-2xl overflow-hidden shadow-2xl border border-slate-200 font-sans flex flex-col min-h-[500px]">
        {/* Header: Signature Razorpay style */}
        <div className="bg-[#121c2c] text-white p-5 flex justify-between items-center relative">
          {/* Top Header details */}
          <div>
            <h3 className="font-bold text-sm tracking-wide flex items-center gap-1.5 text-white">
              <span className="h-2 w-2 rounded-full bg-[#3395FF]" />
              PayShield Secure Gateway
            </h3>
            <p className="text-[10px] text-slate-400 font-medium tracking-wide mt-0.5">
              Pre-Auth Score: <span className="text-[#3395FF] font-mono font-bold">{manualResult?.risk_score || 0.0}</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-[9px] uppercase tracking-wider text-slate-400">Amount</p>
            <p className="font-mono text-base font-extrabold text-white">
              ₹{Number(sandboxPayment.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </p>
          </div>
          <button 
            onClick={onPaymentFailure}
            className="absolute top-2 right-2 text-slate-400 hover:text-white text-xs font-mono px-1 border-none bg-transparent cursor-pointer"
          >
            ✕
          </button>
        </div>
        
        {/* Main checkout frame */}
        <div className="flex-1 flex flex-col min-h-[360px]">
          {paymentState === "idle" && (
            <div className="flex-1 flex min-h-[360px]">
              {/* Left Sidebar Menu */}
              <div className="w-[130px] border-r border-slate-200 bg-[#f1f5f9] flex flex-col">
                <button
                  type="button"
                  onClick={() => setRazorpayTab("card")}
                  className={`flex flex-col items-center justify-center py-4 px-2 text-center border-b border-slate-200 transition-all cursor-pointer ${
                    razorpayTab === "card"
                      ? "bg-white text-[#3395FF] font-bold border-l-4 border-l-[#3395FF]"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <span className="text-lg">💳</span>
                  <span className="text-[10px] uppercase font-bold tracking-wider mt-1.5">Card</span>
                </button>
                <button
                  type="button"
                  onClick={() => setRazorpayTab("upi")}
                  className={`flex flex-col items-center justify-center py-4 px-2 text-center border-b border-slate-200 transition-all cursor-pointer ${
                    razorpayTab === "upi"
                      ? "bg-white text-[#3395FF] font-bold border-l-4 border-l-[#3395FF]"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <span className="text-lg">📱</span>
                  <span className="text-[10px] uppercase font-bold tracking-wider mt-1.5">UPI / QR</span>
                </button>
                <button
                  type="button"
                  onClick={() => setRazorpayTab("netbanking")}
                  className={`flex flex-col items-center justify-center py-4 px-2 text-center border-b border-slate-200 transition-all cursor-pointer ${
                    razorpayTab === "netbanking"
                      ? "bg-white text-[#3395FF] font-bold border-l-4 border-l-[#3395FF]"
                      : "text-slate-600 hover:bg-slate-100"
                  }`}
                >
                  <span className="text-lg">🏦</span>
                  <span className="text-[10px] uppercase font-bold tracking-wider mt-1.5">Netbanking</span>
                </button>
              </div>
              
              {/* Right Tab Content */}
              <div className="flex-1 p-5 flex flex-col justify-between bg-white">
                {/* Tab 1: Cards */}
                {razorpayTab === "card" && (
                  <div className="space-y-3 flex-1">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Card Payment</h4>
                    
                    <div>
                      <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Card Number</label>
                      <input
                        type="text"
                        maxLength={19}
                        value={cardDetails.number}
                        onChange={(e) => {
                          let val = e.target.value.replace(/\D/g, "");
                          val = val.replace(/(.{4})/g, "$1 ").trim();
                          setCardDetails({ ...cardDetails, number: val });
                        }}
                        placeholder="4111 1111 1111 1111"
                        className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-mono outline-none focus:border-[#3395FF] bg-white text-slate-800"
                      />
                    </div>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Expiry</label>
                        <input
                          type="text"
                          maxLength={5}
                          value={cardDetails.expiry}
                          onChange={(e) => {
                            let val = e.target.value.replace(/\D/g, "");
                            if (val.length > 2) {
                              val = val.slice(0, 2) + "/" + val.slice(2, 4);
                            }
                            setCardDetails({ ...cardDetails, expiry: val });
                          }}
                          placeholder="MM/YY"
                          className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-mono outline-none focus:border-[#3395FF] text-center bg-white text-slate-800"
                        />
                      </div>
                      <div>
                        <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">CVV</label>
                        <input
                          type="password"
                          maxLength={3}
                          value={cardDetails.cvv}
                          onChange={(e) => setCardDetails({ ...cardDetails, cvv: e.target.value.replace(/\D/g, "") })}
                          placeholder="•••"
                          className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-mono outline-none focus:border-[#3395FF] text-center bg-white text-slate-800"
                        />
                      </div>
                    </div>
                    
                    <div>
                      <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Cardholder Name</label>
                      <input
                        type="text"
                        value={cardDetails.name}
                        onChange={(e) => setCardDetails({ ...cardDetails, name: e.target.value })}
                        placeholder="John Doe"
                        className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs outline-none focus:border-[#3395FF] bg-white text-slate-800"
                      />
                    </div>
                  </div>
                )}
                
                {/* Tab 2: UPI */}
                {razorpayTab === "upi" && (
                  <div className="space-y-3 flex-1">
                    <div className="flex justify-between items-center">
                      <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">UPI Payment</h4>
                      <button
                        type="button"
                        onClick={() => setQrCodeOption(!qrCodeOption)}
                        className="text-[10px] text-[#3395FF] font-bold hover:underline bg-transparent border-none cursor-pointer"
                      >
                        {qrCodeOption ? "Pay via UPI ID" : "Show QR Code"}
                      </button>
                    </div>
                    
                    {qrCodeOption ? (
                      <div className="flex flex-col items-center justify-center py-1 space-y-2">
                        <div className="bg-white border border-slate-200 rounded-xl p-2.5 shadow-inner relative flex flex-col items-center">
                          <svg className="w-24 h-24 text-slate-800" viewBox="0 0 100 100">
                            <rect width="100" height="100" fill="none" />
                            <rect x="5" y="5" width="25" height="25" fill="none" stroke="currentColor" strokeWidth="8" />
                            <rect x="13" y="13" width="9" height="9" fill="currentColor" />
                            <rect x="70" y="5" width="25" height="25" fill="none" stroke="currentColor" strokeWidth="8" />
                            <rect x="78" y="13" width="9" height="9" fill="currentColor" />
                            <rect x="5" y="70" width="25" height="25" fill="none" stroke="currentColor" strokeWidth="8" />
                            <rect x="13" y="78" width="9" height="9" fill="currentColor" />
                            <rect x="40" y="10" width="10" height="10" fill="currentColor" />
                            <rect x="55" y="15" width="10" height="5" fill="currentColor" />
                            <rect x="40" y="30" width="25" height="10" fill="currentColor" />
                            <rect x="10" y="45" width="15" height="15" fill="currentColor" />
                            <rect x="40" y="45" width="10" height="25" fill="currentColor" />
                            <rect x="55" y="60" width="20" height="10" fill="currentColor" />
                            <rect x="80" y="40" width="15" height="25" fill="currentColor" />
                            <rect x="75" y="75" width="20" height="20" fill="currentColor" />
                          </svg>
                        </div>
                          
                        <div className="text-center">
                          <p className="text-[10px] text-slate-500 font-semibold tracking-wide flex items-center gap-1 justify-center">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            QR Active: <span className="font-mono text-slate-700">{formatTime(qrTimer)}</span>
                          </p>
                          <p className="text-[8px] text-slate-400 mt-0.5">Scan using GPay, PhonePe, Paytm or UPI App</p>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        <div>
                          <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Enter UPI ID / VPA</label>
                          <input
                            type="text"
                            value={upiId}
                            onChange={(e) => setUpiId(e.target.value)}
                            placeholder="alice@upi"
                            className="w-full border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-mono outline-none focus:border-[#3395FF] bg-white text-slate-800"
                          />
                        </div>
                        
                        <div className="grid grid-cols-3 gap-1.5 pt-1">
                          {["Google Pay", "PhonePe", "Paytm"].map((app) => (
                            <button
                              key={app}
                              type="button"
                              onClick={() => setUpiId(`test.${app.toLowerCase().replace(" ", "")}@upi`)}
                              className="border border-slate-200 hover:border-slate-300 hover:bg-slate-50 py-1 px-1.5 rounded-lg text-[9px] font-bold text-slate-600 text-center transition-all bg-white cursor-pointer"
                            >
                              {app}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {/* Tab 3: Netbanking */}
                {razorpayTab === "netbanking" && (
                  <div className="space-y-3 flex-1">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Popular Banks</h4>
                    
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { name: "State Bank of India", code: "SBI" },
                        { name: "HDFC Bank", code: "HDFC" },
                        { name: "ICICI Bank", code: "ICICI" },
                        { name: "Axis Bank", code: "AXIS" }
                      ].map((bank) => (
                        <button
                          key={bank.code}
                          type="button"
                          onClick={() => console.log(`Selected ${bank.name} for netbanking.`)}
                          className="border border-slate-200 hover:border-[#3395FF] hover:bg-[#3395FF]/5 p-2 rounded-xl flex flex-col items-center justify-center text-center transition-all bg-white cursor-pointer group"
                        >
                          <span className="font-bold text-xs text-[#121c2c] group-hover:text-[#3395FF]">{bank.code}</span>
                          <span className="text-[8px] text-slate-500 font-medium mt-0.5">{bank.name}</span>
                        </button>
                      ))}
                    </div>
                    
                    <div>
                      <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Select Other Bank</label>
                      <select className="w-full border border-slate-200 rounded-lg px-2 py-1.5 text-xs outline-none focus:border-[#3395FF] bg-white text-slate-800">
                        <option>Kotak Mahindra Bank</option>
                        <option>Punjab National Bank</option>
                        <option>Canara Bank</option>
                        <option>Union Bank of India</option>
                      </select>
                    </div>
                  </div>
                )}
                
                {/* Action button at bottom */}
                <div className="pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => {
                      setPaymentState("processing");
                      setTimeout(() => {
                        setPaymentState("otp");
                      }, 1500);
                    }}
                    className="w-full bg-[#3395FF] hover:bg-[#1a7ee5] text-white py-2 rounded-xl text-xs uppercase font-extrabold tracking-wider transition-all active:scale-[0.98] shadow-md shadow-[#3395FF]/20 cursor-pointer"
                  >
                    Pay ₹{Number(sandboxPayment.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                  </button>
                </div>
              </div>
            </div>
          )}
          
          {/* State 2: Processing Loader */}
          {paymentState === "processing" && (
            <div className="flex-1 bg-white p-6 flex flex-col items-center justify-center space-y-4 text-center min-h-[360px]">
              <div className="relative w-12 h-12 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-slate-100" />
                <div className="absolute inset-0 rounded-full border-4 border-t-[#3395FF] animate-spin" />
              </div>
              <div>
                <h4 className="font-bold text-slate-800 text-sm">Processing Payment...</h4>
                <p className="text-xs text-slate-400 mt-1">Please do not refresh or close the page.</p>
              </div>
              <div className="text-[10px] text-slate-400 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-100 font-mono">
                Communicating with banking networks...
              </div>
            </div>
          )}
          
          {/* State 3: OTP Page (3D-Secure Bank Verification Portal) */}
          {paymentState === "otp" && (
            <div className="flex-1 bg-white p-6 flex flex-col justify-between min-h-[360px]">
              <div className="space-y-4">
                <div className="border border-slate-200 rounded-xl bg-slate-50 p-3.5 border-l-4 border-l-amber-500">
                  <h4 className="text-[10px] font-extrabold uppercase tracking-wider text-slate-700">Bank 3D-Secure Portal</h4>
                  <p className="text-[9px] text-slate-500 mt-1 leading-relaxed">
                    A verification code has been sent to your registered mobile ending in <strong>*8899</strong>. Enter it below to authorize this transaction of <strong>₹{Number(sandboxPayment.amount).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</strong> at PayShield.
                  </p>
                </div>
                
                <div className="space-y-2">
                  <label className="text-[9px] uppercase font-bold text-slate-500 block mb-1">Enter 6-Digit OTP</label>
                  <input
                    type="text"
                    maxLength={6}
                    value={otpCode}
                    onChange={(e) => {
                      setOtpError("");
                      setOtpCode(e.target.value.replace(/\D/g, ""));
                    }}
                    placeholder="••••••"
                    className="w-full border border-slate-200 rounded-lg px-4 py-2 text-center text-lg font-mono tracking-[0.4em] outline-none focus:border-[#3395FF] bg-white text-slate-800"
                  />
                  {otpError && (
                    <p className="text-red-500 text-[9px] font-bold">{otpError}</p>
                  )}
                </div>
                
                <div className="text-[9px] text-slate-500 italic bg-[#fef3c7]/50 text-[#854d0e] p-2.5 rounded-lg border border-[#fef3c7]">
                  💡 Type <strong className="font-mono">123456</strong> to simulate success. Type anything else (or click failure) to simulate payment cancellation.
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    if (otpCode === "123456") {
                      setPaymentState("success");
                      setTimeout(() => {
                        handleSimulateSuccess();
                      }, 1500);
                    } else {
                      setOtpError("Invalid verification code. Please try again.");
                    }
                  }}
                  className="bg-emerald-400 text-slate-900 hover:bg-emerald-500 font-extrabold text-[10px] uppercase py-2.5 rounded-xl transition-all shadow-md shadow-emerald-400/20 active:scale-[0.98] cursor-pointer"
                >
                  Submit OTP
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setPaymentState("failed");
                    setTimeout(() => {
                      handleSimulateFailure();
                    }, 1500);
                  }}
                  className="border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100 font-extrabold text-[10px] uppercase py-2.5 rounded-xl transition-all active:scale-[0.98] cursor-pointer"
                >
                  Cancel Payment
                </button>
              </div>
            </div>
          )}
          
          {/* State 4: Success checkmark animation */}
          {paymentState === "success" && (
            <div className="flex-1 bg-white p-6 flex flex-col items-center justify-center space-y-4 text-center min-h-[360px]">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 border-2 border-emerald-500 flex items-center justify-center text-emerald-500 text-xl font-bold animate-bounce">
                ✓
              </div>
              <div>
                <h4 className="font-extrabold text-emerald-500 text-sm">Payment Successful!</h4>
                <p className="text-xs text-slate-400 mt-1">Settling transaction securely with PayShield Pre-Auth.</p>
              </div>
            </div>
          )}
          
          {/* State 5: Failure screen */}
          {paymentState === "failed" && (
            <div className="flex-1 bg-white p-6 flex flex-col items-center justify-center space-y-4 text-center min-h-[360px]">
              <div className="w-12 h-12 rounded-full bg-rose-500/10 border-2 border-rose-500 flex items-center justify-center text-rose-500 text-xl font-bold animate-pulse">
                ✕
              </div>
              <div>
                <h4 className="font-extrabold text-rose-500 text-sm">Payment Failed / Cancelled</h4>
                <p className="text-xs text-slate-400 mt-1">The authorization flow was terminated.</p>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer */}
        <div className="bg-slate-50 border-t border-slate-200 py-2.5 text-center">
          <span className="text-[8px] uppercase tracking-widest text-slate-400 font-bold">
            🔒 Razorpay Trusted Security
          </span>
        </div>
      </div>
    </div>
  );
}
