# PayShield: Real-Time Payment Authorization Risk Middleware

PayShield is a pre-transaction fraud prevention platform that fuses **Behavioral Biometrics**, **Device Fingerprinting**, **Machine Learning Anomaly Detection**, and **Graph Intelligence** to stop payment fraud in real-time before money moves.

---

## 🚀 Instant Launch

Start everything with Docker:

```bash
docker-compose up
```

- Dashboard: **http://localhost:5173**
- API docs: **http://localhost:8001/docs**

---

## 🎨 Premium Dashboard Visual Features

- **Ambient Glowing Cyber Aesthetic**: Clean dark HSL theme with glassmorphic cards and subtle pulse animations.
- **Interactive SVG Fraud Graph**: Real-time network map linking users, device hashes, and target accounts. It visually highlights mule accounts and compromised rings with neon glowing pulses.
- **Live Scored Transaction Console**: Select any of the four pre-configured scenarios to watch the Scoring and Fusion Pipeline compute scores step-by-step.
- **Explainable Decisions**: View a multi-signal radar graph showing how individual scoring sub-modules aggregated into the final Allowance/Blocking decisions.
- **Live Deep-Traffic Terminal**: A rolling console feed in the footer streaming transactions and backend pipeline operations in real-time via Server-Sent Events (SSE).

---

## 🧪 Controlled Verification Cases Included

- **Account Takeover (ATO)**: New device from Nigeria, high value transfer to newly added beneficiary. Expected: `BLOCK`.
- **Fraud Ring Detected**: Ring member shares device fingerprint with multiple compromised accounts. Expected: `REVIEW` or `BLOCK`.
- **Safe Payment ✓**: Alice’s regular morning UPI transfer on trusted device. Expected: `ALLOW`.

---

## 📂 Project Directory Structure

### Backend (`backend/app/`)
- `routers/`: Modular endpoint handlers
  - `scoring.py`: Main risk scoring pipeline, including idempotency key checks (`X-API-Key` required when auth is enabled).
  - `identity.py`: Session, device registration, and biometrics data collection.
  - `dashboard.py`: System stats, alerts SSE stream, fraud graph, and metrics.
  - `cases.py`: Cases review and analyst action resolution.
  - `payments.py`: Simulated Razorpay payment flow order integration.
  - `health.py`: Liveness (`/health`) and readiness (`/ready`) checks verifying DB, Redis, and ML model states.
- `middleware/`:
  - `auth.py`: Header-based `X-API-Key` verification (autoseeds `default-dev` / `dev-secret`).
  - `rate_limit.py`: IP/Key rate limiter.
- `services/`:
  - `audit.py`: Structured JSON logger and DB audit trail logging.
  - `sse.py`: Server-Sent Events broker.

### Frontend (`frontend/src/`)
- `components/`:
  - `DiagnosticsPanel.jsx`: Visualizes system latencies and active ML model registry metrics.
  - `RiskScorePanel.jsx`: Renders explainable decision reason codes dynamically.
  - `TransactionForm.jsx`: Captures keystroke, mouse, and scroll events in real-time.
  - `RazorpayModal.jsx`: Simulates Razorpay checkout interface.

---

## ⚙️ Running Automated Backend Tests & Benchmarks

Run unit and integration tests:
```bash
cd backend
python -m pytest tests/ -v
```

Run stress/load test benchmarks:
```bash
python scripts/load_test.py
```
