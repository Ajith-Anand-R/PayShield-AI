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

## 🧪 Simulation Scenarios Included

- **Account Takeover (ATO)**: New device from Nigeria, high value transfer to newly added beneficiary. Expected: `BLOCK`.
- **Fraud Ring Detected**: Ring member shares device fingerprint with multiple compromised accounts. Expected: `DELAY` or `BLOCK`.
- **Safe Payment ✓**: Alice’s regular morning UPI transfer on trusted device. Expected: `ALLOW`.

---

## ⚙️ Running Automated Backend Tests

You can run our in-memory unit test suite using `pytest`:

```bash
cd backend
.venv\Scripts\python -m pytest tests/test_engines.py
```
*All tests pass with 100% correctness.*
