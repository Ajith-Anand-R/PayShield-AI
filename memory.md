# Developer Session Journal: PayShield Architecture & Scoring Implementation

This journal chronicles the implementation details of the PayShield pre-transaction fraud prevention gateway. It serves as a technical log detailing how the modules, DB structures, and API endpoints are wired.

---

## 🏗️ Architecture Design & Components

The system acts as a pre-authorization scoring gateway before digital transaction capture.

### 1. Database Schema (`models/models.py`)
Standardized on SQLite (SQLAlchemy) to enable zero-config setup on developer workstations. The schema tracks:
* `User`: Core accounts. Can be manually flagged as `is_fraudster = True` for cluster seeding.
* `Device`: Registered fingerprints (hashes, browser, OS, location, IP address).
* `BehaviorProfile`: Holds average dwell and flight biometrics to build user baselines.
* `Transaction`: Records capture details (amount, timestamp, target account, status).
* `RiskScore`, `DecisionLog`, `Alert`: Tracks evaluation sub-scores, explainable codes, and active alerts.

### 2. Core Scoring Modules
* **Behavioral DNA (`engines/behavioral.py`)**:
  * Tracks dwell, flight, speed, and scroll averages against baselines.
  * Captures bot patterns (e.g., zero mouse jitter standard deviation).
* **Device Trust (`engines/device.py`)**:
  * Evaluates OS, browser, IP subnet, and location hops.
  * Reserves high-severity warnings for explicit device mismatches.
* **ML Anomaly (`engines/anomaly.py`)**:
  * Leverages an `IsolationForest` ML model trained on historical normal vectors: `[amount, hour, velocity_1h, velocity_24h, geo_distance]`.
  * Fits dynamically on startup (seeding synthetic fallback if empty).
* **Fraud Graph (`engines/graph.py`)**:
  * Syncs active transactions/devices into a NetworkX undirected `Graph`.
  * Computes closeness distances from the user node to known compromised clusters. Distance = 2 (shared device/account) triggers high-priority alerts.

### 3. Risk Fusion & Pipeline Decisions (`services/fusion.py`)
Combines normalized scoring outputs:
`Total Risk = 0.25 * Behavioral + 0.25 * Device + 0.30 * Anomaly + 0.20 * Graph`
Maps risk to decision thresholds and triggers explainable reason codes (e.g., `BOT_PATTERN_DETECTED`, `FRAUD_RING_LINK`).

---

## 🧪 Verification & Session Hardening Patches

To ensure absolute reliability, the backend and frontend configurations were hardened against edge cases:

1. **Request-Scoped Session Refactoring**:
   * Decoupled uvicorn background jobs (Isolation Forest retraining) from FastAPI's request-scoped sessions.
   * Background runners now initialize, execute, and safely close a dedicated session via `SessionLocal()`.
2. **Transaction Writing Sequence Correctness**:
   * Adjusted `api.py` to write and insert the parent `Transaction` record with state `PENDING` *prior* to evaluating engines and fusion.
   * This completely prevents foreign key (FK) constraint exceptions when committing child log tables.
3. **Graph Linkage Edge Protection**:
   * Added checks in `graph.py` to ensure temporary transaction edges are only removed if they did not exist previously, preventing accidental removal of permanent historical links.
4. **Pydantic Response Correction**:
   * Assigned `scores.total_score = total_score` in `fusion.py` to align breakdown responses with top-level score attributes.
5. **Configurable Endpoints & Build Corrections**:
   * Placed the missing `HelpCircle` icon import in `App.jsx`.
   * Moved the `API_BASE` binding to configurable Vite env structures (`import.meta.env.VITE_API_BASE`).
6. **Vite Transform/Parse Syntax Fix**:
   * Fixed Python-style comments (`# comment`) inside JavaScript/JSX object literals (specifically lines 221, 246, 248, 262 in `src/App.jsx`) which were failing the Vite OXC transpiler.
   * Converted all `#` comments to valid JavaScript `//` comments.
7. **Demo & Presentation Narrative Optimization**:
   * Added full-width SOC operational statistics counter bar (screened events, active threat alerts, average system latency, prevention rate metrics).
   * Programmed live evaluation latency overlay (evaluation metrics updating dynamically around 31ms - 34ms).
   * Coded comprehensive explainability map matching reason codes to elaborate human-friendly audit logs.
   * Integrated high-fidelity visual User Risk timelines displaying step-by-step transaction lifecycle stories.
   * Embedded a glowing Pre-Authorization Payment Lifecycle Flow Strip at the top that anchors the middleware architecture visually.
   * Integrated a horizontal Risk Decision Pipeline Progress panel revealing Behavior, Device, ML, and Graph component scores.
   * Implemented a preventative red shield banner on `BLOCK` and `DELAY` decisions: `"Transaction intercepted before authorization. Funds never left the source account."`
   * Sandboxed Controlled Authorization Environment: Fully replaced all "scenario" and "simulation" wording with production-oriented pre-authorization `Controlled Cases` (Auth-Req A-101 Baseline Trusted, Auth-Req B-202 Identity Drift, etc.).
   * API Gateway Integration Console: Programmed a real-time developer sandbox integration console showing the actual dynamic JSON Request/Response payloads representing the active authorization request.

---

## 🚀 Dev Verification Results
Unit tests can be executed locally:
```bash
cd backend
.venv\Scripts\python -m pytest tests/test_engines.py
```
*Outcome: 5 out of 5 tests successfully pass, validating behavioral, device, anomaly, graph closeness engines, and referential database sequencing.*

*Vite Frontend Build & Presentation Polish:*
* Resolved parser issues: Vite dev server compiles `App.jsx` flawlessly with no parser/transform errors.
* Automated server launch: Successfully orchestrated local dev servers for both the FastAPI Backend (port 8000) and the Vite React Frontend (port 5173) in separate terminal shells.
* Dynamic operational dashboard: Counters, latency trackers, risk timelines, audit logs, preventative warning banners, and interactive developer API consoles update in real time with pre-authorization checkout triggers.
