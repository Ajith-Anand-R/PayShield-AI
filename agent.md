# PayShield — Engineering Agent Brief (`agent.md`)

> **Audience:** an autonomous coding agent (Gemini) that will execute this plan.
> **Goal:** turn the current PayShield prototype into a **production-grade, real-time digital-payment fraud-prevention middleware** that directly satisfies the hackathon problem statement.
> **Golden rule:** *Be honest. Every metric shown to a judge or user must be measured, not hardcoded.* Delete fake numbers. Prove claims with code and tests.

---

## 0. Read this first — operating rules for the agent

1. **Do not rewrite from scratch.** ~70% of this is good. Refactor and harden it. Preserve the engine architecture, the graph intelligence, the SSE feed, and the DB schema.
2. **Work in phases (Section 4).** Finish and verify a phase before starting the next. Each phase has explicit **Acceptance Criteria** — do not move on until they pass.
3. **Never fake a metric.** If you can't measure latency/accuracy/false-positive rate honestly, build the measurement first.
4. **Every behavior you change must have a test** that exercises the *real* code path (not a bypassed one).
5. **Run the full test suite after every phase:** `cd backend && .venv\Scripts\python -m pytest -q`. Keep it green.
6. **Keep commits small and labeled by phase** (e.g. `[P1] remove per-txn retraining`).
7. When a doc (`idea.md`, `README.md`, `memory.md`) disagrees with code, **code is the truth** — update the docs, don't trust them.

---

## 1. What PayShield is (the target product)

A **pre-authorization fraud-risk middleware**. A bank core / payment switch / wallet calls PayShield *before* finalizing a payment. PayShield returns, in **<50ms (measured)**, a risk score `0–100`, a decision, explainable reason codes, and a sub-score breakdown.

**Decision taxonomy — pick ONE canonical set and use it everywhere (code, DB, API, UI):**

| Score band | Decision (canonical) | Meaning |
|-----------|----------------------|---------|
| `0–30`    | `ALLOW`              | Approve immediately |
| `30–55`   | `STEP_UP`            | Challenge (OTP / biometric / PIN) |
| `55–80`   | `REVIEW`             | Hold in queue for analyst / delayed settlement |
| `80–100`  | `BLOCK`              | Reject before money moves |

> **Current code uses `APPROVE/REVIEW/HOLD` and maps to `ALLOWED/STEP_UP_REQUIRED/BLOCKED`.** This is inconsistent with the docs and confusing. **Standardize on `ALLOW / STEP_UP / REVIEW / BLOCK` across the whole stack** (Section 4, Phase 2).

**Six signals fused into one score:**
1. **Behavioral DNA** — keystroke dwell/flight, mouse speed/jitter, scroll velocity; bot detection.
2. **Device Trust** — fingerprint, new/shared/rare device, IP & location mismatch.
3. **Geolocation** — new location, city/country change, impossible-travel via haversine.
4. **Transaction Anomaly** — amount ratio, hour, velocity (1h/24h), geo-distance, new-beneficiary.
5. **Graph Intelligence** — distance-to-known-fraud, circular flow, layering, hub/funnel (mule) patterns.
6. **Scam-text (LLM)** — Gemini classification of the transaction remark.

---

## 2. Current codebase map (ground truth as of this brief)

```
PayShield/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + lifespan (trains ALL models on startup)
│   │   ├── config.py               # weights + thresholds (plain class, no env loading)
│   │   ├── database.py             # SQLite default / DATABASE_URL override
│   │   ├── models/models.py        # SQLAlchemy ORM (good schema, see Section 3)
│   │   ├── schemas/schemas.py      # Pydantic request/response
│   │   ├── schemas/stream_schemas.py
│   │   ├── routes/api.py           # ALL endpoints (monolithic, ~800 lines)
│   │   ├── engines/
│   │   │   ├── behavioral.py       # RandomForest + heuristic fallback
│   │   │   ├── device.py
│   │   │   ├── geolocation.py
│   │   │   ├── anomaly.py          # brute-forces "100% accuracy" — REMOVE this
│   │   │   ├── graph.py            # NetworkX DiGraph, rebuilt per call
│   │   │   ├── training.py         # synthetic data gen + train_all_engines
│   │   │   └── *.pkl               # committed model artifacts — REMOVE from git
│   │   ├── services/
│   │   │   ├── fusion.py           # meta-classifier + decision + reason codes
│   │   │   ├── scam_detector.py    # Gemini + local heuristic fallback
│   │   │   └── redis_client.py     # real Redis + in-memory fallback
│   │   └── scratch_db.py           # scratch file — REMOVE
│   ├── tests/test_engines.py       # tests run with ML BYPASSED (is_test flag)
│   ├── payshield.db                # committed SQLite DB — REMOVE from git
│   ├── Dockerfile                  # python:3.11-slim, port 8001
│   └── requirements.txt
├── frontend/                       # React 19 + Vite + Tailwind + d3 + recharts
│   └── src/App.jsx                 # 843-line monolith — needs decomposition
├── docker-compose.yml
├── start.bat
├── idea.md / README.md / memory.md # partly stale — reconcile with code
└── graphify-out/                   # tool output — gitignore it
```

### Known leftovers / inconsistencies to clean (Phase 0)
- Deleted-but-referenced: `stream_generator.py`, `LiveMonitor.jsx`, `ScenarioController.jsx` (git shows `D`). Confirm no imports remain.
- Untracked new files: `geolocation.py`, `training.py`, `scam_detector.py`, `AuthScreen.jsx`, `InvestigationConsole.jsx`, `scratch_db.py`, all `*_model.pkl`. Decide keep vs remove (see Phase 0).
- Port confusion: README says API `8001`, CORS allows only `5173`, frontend `API_BASE` defaults to `8001`. **Standardize on `8001`** and document it.
- `config.py` `DATABASE_URL` default is a fake `postgresql://user:pass@...` string used as a sentinel in `database.py`. Replace with proper env-based settings.

---

## 3. Data model (keep — it's good). Add these.

Current tables (in `models/models.py`): `User, Device(device_profiles), BehaviorProfile, Session, Beneficiary, Transaction, RiskScore, GraphEdge, Alert, DecisionLog, FraudCase`. **Keep all.**

**Add:**
- `ApiClient` — `id, name, api_key_hash, is_active, rate_limit_per_min, created_at`. For authenticating callers (Phase 5).
- `ModelRegistry` — `id, model_name, version, trained_at, metrics_json (precision/recall/f1/auc/fpr), is_active, artifact_path`. So you never again ship an unevaluated model.
- `AuditLog` — `id, actor, action, entity, entity_id, timestamp, detail_json`. Regulatory reporting requirement in the PS.
- On `Transaction`: add `latency_ms (Float)` so you store the **real** measured scoring latency per transaction.

**Migrations:** introduce **Alembic** now (Phase 1). `Base.metadata.create_all` is fine for SQLite dev but not for evolving a production Postgres schema.

---

## 4. The plan — phased execution

### Phase 0 — Repo hygiene & honesty pass (fast, do first)

**Remove / git-ignore (these should never be in version control):**
- `backend/payshield.db`, root `payshield.db`, `backend/payshield_graph.pkl`, root `payshield_graph.pkl`
- All `backend/app/engines/*_model.pkl`
- `backend/app/scratch_db.py`
- `graphify-out/`, `__pycache__/`, `.pytest_cache/`, `backend/.venv/`, `frontend/dist/`, `node_modules/`

**Create a real root `.gitignore`** covering Python, Node, venvs, DBs, pkl artifacts, `.env`, `graphify-out/`.

**Delete fake/demo theater:**
- Any hardcoded latency display in the frontend ("31–34ms"). Replace with the **real** `latency_ms` returned by the API (added in Phase 1).
- The `train_model()` method in `engines/anomaly.py` that loops hyperparameters until it hits `acc >= 1.0`. The "100% accuracy" framing is misleading and must go (replaced in Phase 3).
- Reconcile `idea.md` / `README.md` decision names and thresholds with the canonical set in Section 1.

**Acceptance:** `git status` is clean of binaries/DBs; repo builds; no dead imports (`grep -r stream_generator backend/app` returns nothing).

---

### Phase 1 — Performance & correctness backbone (highest priority)

This phase makes the product's core claim ("real-time, low latency") *true*.

**1.1 — Kill per-transaction retraining.**
- In `routes/api.py::score_transaction`, **remove** `background_tasks.add_task(retrain_all_engines_bg)`. Training on every transaction is the single worst issue.
- Replace with **scheduled / threshold-based retraining**:
  - A standalone CLI: `python -m app.engines.training` (train once, write artifacts + `ModelRegistry` row).
  - A background scheduler (APScheduler) that retrains every N hours **or** after M new labeled transactions — never inline in the request path.
  - Models are loaded **once** at startup into the in-process singleton; a retrain swaps the artifact and flips `ModelRegistry.is_active`, then triggers a hot-reload.

**1.2 — Measure real latency.**
- Wrap the scoring pipeline with `time.perf_counter()`. Store `latency_ms` on the `Transaction` and return it in `DecisionResponse`.
- Add `GET /api/metrics/latency` returning p50/p95/p99 over recent transactions. The dashboard reads these — no hardcoding.

**1.3 — Single atomic DB transaction per scoring call.**
- **Problem today:** each engine calls `db.commit()` independently (e.g. `behavioral.py` commits baseline, `device.py` commits device, `fusion.py` commits scores). A failure mid-pipeline leaves partial writes.
- **Fix:** engines must **not** commit. They mutate ORM objects / return values only. `score_transaction` does **one** `db.commit()` at the end (or rollback on error). Pass a flag or refactor so baseline-seeding writes are staged, not committed, until the end.

**1.4 — Stop rebuilding the whole graph every transaction.**
- `graph.py::calculate_risk` calls `sync_graph_from_db(db)` every time → O(N) per request.
- **Fix:** keep the NetworkX graph as a warm in-memory singleton, synced at startup and **incrementally updated** (add nodes/edges for the new txn) on each scored transaction. Add a periodic full re-sync (e.g. every 5 min) for drift correction. For `GET /api/graph/data`, serve from the warm graph.

**1.5 — Don't retrain anomaly model lazily inside `calculate_risk`.**
- `anomaly.py::calculate_risk` calls `cls.train_model(db)` if no model is loaded. Training inside a scoring request is unacceptable. Models must be guaranteed-loaded at startup; if missing, fail fast with a clear startup error (or load a shipped default artifact).

**Acceptance:**
- `POST /api/transaction/score` p95 latency **< 50ms** measured locally (warm), returned in the response and visible via `/api/metrics/latency`.
- No `predict`/`fit`/`GridSearchCV` call occurs inside any request handler (grep to confirm).
- Killing the process mid-request leaves no partial DB rows (atomic commit verified by a test).

---

### Phase 2 — Decision taxonomy & explainability consistency

**2.1 — One decision vocabulary** (`ALLOW / STEP_UP / REVIEW / BLOCK`) everywhere:
- `fusion.py` returns these directly. Remove the `APPROVE/REVIEW/HOLD` → `ALLOWED/STEP_UP_REQUIRED/BLOCKED` `status_map` indirection; store the decision verbatim and use a single `Transaction.status` value equal to the decision.
- Update `config.py` thresholds to the Section 1 bands and **load them from env** (see Phase 5 settings). Update `DecisionLog.decision` comment, schemas, frontend.

**2.2 — Reason codes as structured data.**
- Today reason codes are a comma-joined string. Keep the string for back-compat but also return a **structured list of `{code, severity, signal, human_message}`** so the UI and audit logs are unambiguous. Centralize the code→message map in one module (`services/reason_codes.py`).

**2.3 — Score must be able to reach BLOCK.**
- `fusion.py` clamps `total_score` to `99.0` and the heuristic rarely crosses 80 cleanly. Verify each canonical scenario (Section 6) actually lands in its intended band. Tune weights/penalties so a clear fraud (e.g. shared device with known fraudster + scam text + impossible travel) reaches `BLOCK`.

**Acceptance:** every endpoint, DB row, and UI label uses the same 4 decision words; the 4 canonical scenarios each produce the expected decision (asserted in tests).

---

### Phase 3 — Make the ML real and evaluable (the heart of "production grade")

This is what separates a demo from a fraud product. The PS explicitly asks to **reduce false positives** and **adapt to evolving typologies** — both require *real data* and *honest evaluation*.

**3.1 — Bring in a real, labeled dataset (offline training).**
- Use a recognized public fraud dataset for the anomaly/fusion models. Recommended (pick one, document choice):
  - **PaySim** (mobile-money simulation, has fraud labels) — closest to UPI/wallet semantics.
  - **IEEE-CIS Fraud Detection** (rich device/transaction features).
  - **Sparkov / credit-card-transaction** synthetic-but-realistic with geo + merchant.
- Add `backend/data/` (git-ignored) + a `scripts/download_data.py` and `scripts/prepare_dataset.py` that maps the public dataset's columns onto PayShield's feature vectors.
- Keep your synthetic generator (`training.py`) as **augmentation only** (to cover rare typologies under-represented in the public set), not as the primary signal.

**3.2 — Proper train/validation/test split + metrics, persisted.**
- Replace the "loop until 100% accuracy" approach with a **stratified train/val/test split** and **time-based split** where timestamps exist (fraud models must be validated on *future* data to avoid leakage).
- Compute and **store in `ModelRegistry.metrics_json`**: precision, recall, F1, ROC-AUC, PR-AUC, and **false-positive rate at a fixed recall** (e.g. FPR @ 0.80 recall). Print a confusion matrix.
- Add `GET /api/model/metrics` so the dashboard shows the *real* current model performance.
- **Target (be honest, don't fake):** PR-AUC clearly > a logistic-regression baseline; document the FPR you achieve. Do **not** claim 100%.

**3.3 — Remove the test-bypass; test the real path.**
- Every engine currently does: `is_test = "pytest" in sys.modules ...` then skips the ML model. **This means tests never exercise production behavior.**
- **Fix:** delete the `is_test` short-circuits. Instead, in tests, either (a) load a small fixture model trained in a fixture, or (b) inject the model via dependency, so tests run the *same* code path as production. Heuristic fallback should be reachable only when no model artifact exists, and that case should have its own explicit test.

**3.4 — Calibrate probabilities.**
- RandomForest `predict_proba` is not well-calibrated. Wrap final classifiers in `CalibratedClassifierCV` (isotonic/sigmoid) so the `0–100` score is a meaningful probability — critical for threshold tuning and for reducing false positives.

**3.5 — Feedback loop for adaptivity (closes the PS "adapt to evolving fraud" requirement).**
- When an analyst resolves a `FraudCase` (`confirmed` / `false_positive`) via `PATCH /api/cases/{id}`, that label feeds the next scheduled retrain. Wire `extract_real_data` to weight analyst-confirmed labels. This is your concrete "learns over time" story — make sure it actually flows into training data and is demonstrable.

**Acceptance:** `GET /api/model/metrics` returns real precision/recall/FPR from a held-out test set; tests pass against the **real** ML path; no code claims 100% accuracy.

---

### Phase 4 — API surface: clean, documented, contract-stable

**4.1 — Consolidate `routes/api.py`.** It's an ~800-line grab-bag with duplicate endpoints (`/transaction/score`, `/transactions/create`, `/risk/evaluate` all do the same thing; `/behavior/capture` and `/behavior/collect`; `/alerts/live` and `/dashboard/live`). Split into routers:
- `routers/scoring.py` — the one canonical `POST /api/v1/transaction/score` (+ `/webhook/ingest`).
- `routers/identity.py` — register/login/device/behavior/session.
- `routers/dashboard.py` — stats, alerts, live SSE, graph, metrics.
- `routers/cases.py` — fraud case management.
- `routers/payments.py` — Razorpay sandbox.
- **Version the API:** prefix `/api/v1`. Mark duplicates deprecated, then remove.

**4.2 — Lock the request/response contract** with Pydantic and publish it. The `/docs` (OpenAPI) is your integration story for "seamless integration with existing banking ecosystems" — make it clean and example-rich.

**4.3 — Idempotency.** Accept a client-supplied `idempotency_key` on scoring so a retried payment request isn't double-scored / double-logged.

**Acceptance:** one canonical scoring endpoint; OpenAPI docs render cleanly with examples; duplicate endpoints removed or clearly deprecated; idempotency test passes.

---

### Phase 5 — Production concerns: config, auth, rate-limiting, observability

**5.1 — Settings via env.** Replace the plain `config.py` class with `pydantic-settings` `BaseSettings` reading from env / `.env`: DB URL, Redis URL, weights, thresholds, Gemini key, Razorpay keys, retrain interval, CORS origins. Ship `.env.example`.

**5.2 — Authentication & rate-limiting.** A fraud gateway must not be open.
- API-key auth (`X-API-Key` header → `ApiClient.api_key_hash`) on all scoring/ingest endpoints. Dashboard/admin endpoints behind a separate admin key or simple JWT.
- Per-client rate limiting (e.g. `slowapi` or a Redis token bucket).

**5.3 — Structured logging + audit trail.** JSON logs with `transaction_id` correlation. Write `AuditLog` rows for every decision and every case action (regulatory reporting requirement).

**5.4 — Health & readiness.** `GET /health` (liveness) and `GET /ready` (models loaded, DB reachable, Redis reachable).

**5.5 — Real Postgres + Redis in compose.** Verify `docker-compose.yml` actually wires Postgres + Redis + backend + frontend, uses Alembic migrations on boot, and the README's `docker-compose up` works end-to-end on the documented ports.

**Acceptance:** unauthenticated scoring request is rejected; rate limit triggers under load; `/health` and `/ready` behave correctly; `docker compose up` brings the full stack online with Postgres + Redis.

---

### Phase 6 — Frontend: honest, decomposed, demo-ready

**6.1 — Decompose `App.jsx` (843 lines).** Extract the Razorpay sandbox, OTP flow, and tab logic into dedicated components/hooks. Keep state colocated in custom hooks (`useSSE`, `useGraphData`, `useDashboardStats` already exist — extend the pattern).
**6.2 — Show only real data.** Latency, model metrics (precision/recall/FPR), throughput counters must come from the new endpoints (`/api/metrics/latency`, `/api/model/metrics`, `/api/dashboard/stats`). Remove every hardcoded "demo" number.
**6.3 — Explainability UI.** Render the structured reason codes (Phase 2.2): per-signal radar (recharts, already a dep), the decision band, and the human messages. This is the judge-facing "why" panel.
**6.4 — Graph viz.** Keep the d3/SVG fraud-ring map; color nodes by `is_fraudster/is_compromised/is_mule/is_hub/is_funnel` (already provided by `get_graph_data`).
**6.5 — Real behavioral capture.** If you claim behavioral biometrics, capture real keystroke dwell/flight and mouse dynamics in the browser during the transaction form and send them — don't send static averages.

**Acceptance:** no hardcoded metrics remain in the UI; reason codes and sub-scores render from API; `npm run build` succeeds.

---

### Phase 7 — Testing, load, and docs

**7.1 — Unit tests** for every engine on the **real** ML path + the heuristic-fallback path (both explicitly).
**7.2 — Integration tests** for the full `POST /api/v1/transaction/score` pipeline (FastAPI `TestClient`) covering the 4 canonical scenarios (Section 6).
**7.3 — Latency/load test** (e.g. `locust` or a simple async benchmark): assert p95 < 50ms warm, and report throughput. Store results in `docs/PERFORMANCE.md`.
**7.4 — Rewrite the docs** (`README.md`, `idea.md`, `memory.md`) to match reality: real architecture diagram, real metrics, accurate run instructions, the canonical decision taxonomy, and an honest "limitations & future work" section.

**Acceptance:** `pytest` green; load report exists with real numbers; docs match code.

---

## 5. Priority order (do in this sequence)

1. **Phase 0** — hygiene & remove fakes (½ day)
2. **Phase 1** — performance backbone (latency, no inline training, atomic DB, warm graph) — **most important**
3. **Phase 3** — real dataset + honest metrics + remove test-bypass — **second most important**
4. **Phase 2** — decision taxonomy consistency
5. **Phase 4** — API consolidation + versioning
6. **Phase 5** — config/auth/observability
7. **Phase 6** — frontend honesty + decomposition
8. **Phase 7** — tests/load/docs

> If time is short, Phases 0→1→3→2 alone convert this from "demo with fake numbers" to "credible real-time fraud engine with measured performance." That is the defensible core.

---

## 6. Canonical demo scenarios (must pass, asserted in tests)

| # | Scenario | Inputs | Expected decision |
|---|----------|--------|-------------------|
| 1 | **Safe payment** | known device, normal amount, baseline behavior, familiar geo | `ALLOW` (<30) |
| 2 | **Device/identity drift** | new device, IP+city change, mild behavior drift | `STEP_UP` (30–55) |
| 3 | **Bot / midnight anomaly** | 3AM, extreme amount, zero mouse jitter (bot), velocity burst | `REVIEW` or `BLOCK` |
| 4 | **Fraud ring / mule** | device shared with known fraudster + scam remark + impossible travel | `BLOCK` (80+) |

Each must be an integration test asserting the band **on the real ML path**.

---

## 7. Definition of done (production-grade checklist)

- [ ] Scoring p95 latency **< 50ms measured** and surfaced via API + UI (no hardcoded numbers anywhere).
- [ ] No training/`predict` work happens inside a request handler; retraining is scheduled/threshold-based and hot-reloads.
- [ ] Models trained on a **real labeled dataset**; `ModelRegistry` stores precision/recall/F1/ROC-AUC/PR-AUC/**FPR**; metrics exposed via API.
- [ ] Tests exercise the **real ML path** (no `is_test` bypass) and all 4 canonical scenarios pass.
- [ ] One canonical decision vocabulary (`ALLOW/STEP_UP/REVIEW/BLOCK`) across code, DB, API, UI.
- [ ] Single atomic DB commit per scoring call; warm incrementally-updated graph.
- [ ] Env-based settings; API-key auth + rate limiting; structured logging + `AuditLog`; `/health` + `/ready`.
- [ ] Alembic migrations; `docker compose up` runs backend + frontend + Postgres + Redis on documented ports.
- [ ] Analyst case outcomes feed the next retrain (demonstrable adaptive loop).
- [ ] Docs (`README`, `idea`, `memory`) reconciled with code; honest limitations section included.
- [ ] No binaries/DBs/pkl/`.env` in git; real `.gitignore`.

---

## 8. Explicit "remove" list (quick reference)

- `engines/anomaly.py::train_model` brute-force-to-100%-accuracy logic → replace with proper evaluated training (Phase 3).
- `routes/api.py` per-transaction `retrain_all_engines_bg` task (Phase 1.1).
- `is_test` ML-bypass blocks in `behavioral.py`, `device.py`, `geolocation.py`, `anomaly.py`, `graph.py`, `fusion.py` (Phase 3.3).
- Duplicate endpoints: `/transactions/create`, `/risk/evaluate`, `/behavior/collect`, `/dashboard/live`, `/dashboard/alerts` (collapse into canonical ones, Phase 4.1).
- Hardcoded latency/metric displays in `frontend/src/App.jsx` (Phase 0 / 6.2).
- `backend/app/scratch_db.py`, committed `*.pkl`, `payshield.db`, `payshield_graph.pkl`, `graphify-out/` from git (Phase 0).
- `APPROVE/HOLD/STEP_UP_REQUIRED` naming and the `status_map` indirection (Phase 2.1).

---

## 9. Tech stack (target)

- **Backend:** FastAPI (async), SQLAlchemy 2.x + **Alembic**, Pydantic v2 + **pydantic-settings**, scikit-learn (+ `CalibratedClassifierCV`), NetworkX, Redis, APScheduler, slowapi.
- **ML data:** PaySim **or** IEEE-CIS **or** Sparkov (pick one, document it), synthetic augmentation for rare typologies.
- **Frontend:** React 19 + Vite + Tailwind + d3 + recharts + FingerprintJS (already present).
- **Infra:** Docker Compose (backend + frontend + Postgres + Redis). Pin **Python 3.11** (the Dockerfile already does — note the local venv uses 3.14; standardize on 3.11/3.12 to avoid bleeding-edge package breakage).

---

*End of brief. Execute phase by phase. Keep tests green. Show only numbers you measured.*
