# Performance & Latency Report

Calculated on 2026-06-24 19:05:50

## Methodology
The load test evaluates ASGI pipeline processing overhead for real-time transaction scoring under concurrent load. The benchmark runs against the core `POST /api/scoring/transaction/score` scoring endpoint, exercising:
1. Pydantic request validation and dependency resolution.
2. In-memory SQLite session transaction logging.
3. Feature extraction across all five engines (Behavioral, Device, Geolocation, Anomaly, Graph).
4. Machine Learning model inference (Random Forest classifier pipeline).
5. Explainability analysis, decision scoring, Server-Sent Events (SSE) broadcasting, and audit logging.

## Benchmark Configuration
- **Total Requests**: 100
- **Concurrency**: 1
- **Database Engine**: SQLite
- **Redis Mode**: In-Memory client mock

## Results
| Metric | Value |
| :--- | :--- |
| **Throughput** | 25.94 req/sec |
| **Total Test Duration** | 3.85 seconds |
| **Successful Requests** | 100 |
| **Failed Requests** | 0 |
| **Min Latency** | 29.84 ms |
| **Average Latency** | 38.49 ms |
| **p50 Latency** | 37.87 ms |
| **p95 Latency** | 46.15 ms |
| **p99 Latency** | 59.25 ms |
| **Max Latency** | 59.45 ms |

## Verification
- **p95 Latency SLA Check**: ✅ PASSED (Under 50ms SLA)
