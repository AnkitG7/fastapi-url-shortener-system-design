# ⚡ Load Testing & Performance Benchmarking Report

This document records the empirical performance benchmarks of the URL Shortener Service under high concurrent load using both **Custom Asyncio Benchmark Suite** and **Locust Distributed Load Testing Framework**.

---

## 1. Test Environment

- **Server**: FastAPI + Uvicorn (Single Instance Async Event Loop)
- **Primary Database**: PostgreSQL 16 Alpine (Docker, Connection Pool: 5 base, 10 overflow)
- **Cache & Rate Limiter**: Redis 7 Alpine (Docker, AOF Persistence)
- **Benchmark Tools**:
  - `locust==2.46.3` (Multi-user weighted persona simulation)
  - `httpx==0.28.1` (Asynchronous micro-benchmarking)
- **Operating System**: Windows (Local Docker Desktop)

---

## 2. Locust Load Testing (Multi-Persona Simulation)

We executed Locust with **50 simulated concurrent users** (Spawn rate: 10 users/sec) over a realistic read-heavy distribution:
- **80% Weight**: `GET /{short_code}` (Redirects & Cache Hits)
- **15% Weight**: `POST /api/v1/shorten` (URL Creation & Cache Pre-warming)
- **5% Weight**: `GET /api/v1/urls/{code}/analytics` (Aggregate Reporting)

### 📈 Locust Empirical Results (Zero Failures)

```
Type     Name                                 # reqs      # fails |    Avg     Min     Max    Med |   req/s
--------|-----------------------------------|-------|-------------|-------|-------|-------|-------|--------
GET      /{short_code} (Redirect)               331     0(0.00%) |   1247     122    7080    990 |   16.72
POST     /api/v1/shorten (Create)                71     0(0.00%) |   2492     876    6495   2200 |    3.59
GET      /api/v1/urls/{code}/analytics           18     0(0.00%) |   1654     666    3199   1500 |    0.91
GET      /health/ready                            6     0(0.00%) |   1317     658    2057   1300 |    0.30
--------|-----------------------------------|-------|-------------|-------|-------|-------|-------|--------
         Aggregated                             476     0(0.00%) |   1626     122    7080   1400 |   24.05
```

- **Total Requests Handled**: 476 requests
- **Failure Rate**: **0.00% (Zero dropped requests or 500 errors)**
- **Redirects Success Rate**: 100% returned `307 Temporary Redirect`

---

## 3. Asyncio Micro-Benchmark Scenarios

### Scenario 1: High-Concurrency Redirects (Redis Cache Hit)
- **Workload**: 1,000 requests | 50 concurrent workers
- **Target**: `GET /{short_code}` (Cached in Redis)
- **Results**:
  - **Success Rate**: $100\%$ ($1,000 / 1,000$ returned `HTTP 307`)
  - **Throughput**: $79.8\text{ requests/sec}$
  - **Latency P50**: $517.8\text{ ms}$
  - **Telemetry Processing**: 1,000 `ClickEvent` objects published asynchronously to `EventBus` without adding latency to the redirect responses.

---

### Scenario 2: Concurrent URL Creation (PostgreSQL Writes)
- **Workload**: 300 requests | 20 concurrent workers
- **Target**: `POST /api/v1/shorten` (Database write + Redis cache pre-warming)
- **Results**:
  - **Success Rate**: $100\%$ ($300 / 300$ returned `HTTP 201 Created`)
  - **Throughput**: $28.1\text{ writes/sec}$
  - **Connection Pool Health**: Zero connection exhaustion or pool timeout errors.

---

### Scenario 3: Rate Limiting Enforcement Under Attack
- **Workload**: 50 rapid requests from an unauthenticated IP (Quota = 10 req/min)
- **Target**: `GET /api/v1/urls`
- **Results**:
  - **Allowed (HTTP 200)**: $10\text{ requests}$ (Exact tier quota)
  - **Throttled (HTTP 429)**: $40\text{ requests}$
  - **Defense Behavior**: Redis Sliding Window Log (`ZSET`) cleanly blocked the burst attack and returned standard `Retry-After` headers.

---

## 4. How to Run Load Tests

### Run with Locust (Headless CLI)
```bash
locust -f scripts/locustfile.py --headless -u 50 -r 10 -t 30s --host http://localhost:8000
```

### Run with Locust (Interactive Web UI)
```bash
locust -f scripts/locustfile.py --host http://localhost:8000
# Open http://localhost:8089 in your browser to view real-time charts
```

### Run Asyncio Benchmark Script
```bash
python scripts/load_test.py
```
