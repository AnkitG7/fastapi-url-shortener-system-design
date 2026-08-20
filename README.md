# 🔗 FastAPI URL Shortener — Production System Design Project

A **production-grade URL Shortener Service** built with FastAPI, PostgreSQL, Redis, and Nginx, designed to teach **20+ core system design concepts** through hands-on code.

Every file is heavily commented with explanations of **WHY** design decisions were made.

---

## 🎯 System Design Concepts Covered (7 Phases)

| Phase | Core Concepts | Status |
|-------|---------------|:------:|
| **1. API Design** | REST principles, Pydantic Data Contracts, Pagination, 301 vs 307 Redirects, HTTP Status Codes | ✅ Complete |
| **2. Database Layer** | Relational Schema Design, B-Tree Indexing, Connection Pooling, Repository Pattern, Alembic Migrations | ✅ Complete |
| **3. Caching & Performance** | Redis Cache-Aside (Lazy Load), Pre-Warming, TTL Expiration, Cache Invalidation, Graceful Degradation | ✅ Complete |
| **4. Auth, Rate Limiting & Security** | Sliding Window Log (Redis ZSET), Tiered API Keys, RFC Headers (`Retry-After`), SSRF Defense | ✅ Complete |
| **5. Async Processing & Analytics** | Producer-Consumer Pattern, EventBus, Background Batch Worker, Bulk Inserts, CQRS Aggregations | ✅ Complete |
| **6. Observability & Reliability** | Structured JSON Logging, Distributed Tracing (`X-Correlation-ID`), `/health/ready` Probes, Circuit Breaker | ✅ Complete |
| **7. Scaling & Deployment** | Multi-Stage Dockerfile, Horizontal Scaling, Nginx Round-Robin Load Balancing, Capacity Estimations | ✅ Complete |

---

## 🏛️ System Architecture

```
                    [ Client / Browser ]
                             |
                             v
                  [ Nginx Load Balancer ]
                   (Port 80 -> Round Robin)
                 /           |           \
                v            v            v
          [App Replica 1] [App Replica 2] [App Replica 3]
               \             |             /
                +------------+------------+
                |                         |
                v                         v
          [ PostgreSQL ]              [ Redis ]
          (Durable DB)           (Cache & Rate Limit)
```

---

## 🚀 Quick Start (Production Multi-Container Cluster)

### 1. Launch with Docker Compose
```bash
# Start full stack: Nginx (Port 80), 3 App Replicas, PostgreSQL, and Redis
docker compose up --build -d
```

### 2. Verify Everything is Running
```bash
# Check service health
curl http://localhost/health/ready
```

### 3. Open Interactive Swagger Docs
Navigate to: **[http://localhost/docs](http://localhost/docs)**

---

## 🧪 Run Automated Test Suite (79 Tests)

```bash
# Activate local virtual environment
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/Mac

pytest tests/ -v
```

```
============================= 79 passed in 14.97s =============================
```

---

## 📁 Project Structure

```
├── alembic/                 # Database migrations (schema version control)
│   ├── versions/            # Migration scripts
│   └── env.py               # Migration environment configuration
├── app/
│   ├── main.py              # FastAPI entry point, middleware, multi-resource lifecycle
│   ├── dependencies.py      # Dependency injection (Auth, Rate Limiter, DB, Cache, Service)
│   ├── core/
│   │   ├── config.py        # Type-safe configuration (Pydantic Settings)
│   │   ├── logging_config.py# Structured JSON logging formatter with contextvars
│   │   └── security.py      # SSRF defense, private IP filtering, UserTier enum
│   ├── db/
│   │   ├── database.py      # Async engine, connection pooling, session factory
│   │   └── models.py        # SQLAlchemy ORM models (urls & clicks tables)
│   ├── cache/
│   │   ├── redis_client.py  # Async Redis client, connection pooling, health checks
│   │   └── url_cache.py     # Cache-Aside pattern, TTL, namespacing, graceful degradation
│   ├── events/
│   │   └── event_bus.py     # In-memory Producer-Consumer queue with bounded backpressure
│   ├── workers/
│   │   └── analytics_worker.py # Async Background Worker for batch bulk inserts
│   ├── middleware/
│   │   ├── auth.py          # API key authentication & tier resolution
│   │   ├── rate_limiter.py  # Redis Sliding Window Log rate limiter via Sorted Sets
│   │   ├── logging_middleware.py # Request tracing (X-Correlation-ID) & latency logging
│   │   └── circuit_breaker.py   # Circuit breaker pattern (CLOSED/OPEN/HALF_OPEN)
│   ├── repositories/
│   │   └── url_repository.py# Data Access Layer (Atomic updates, CRUD)
│   ├── services/
│   │   ├── url_service.py   # Business Logic Layer (Cache-Aside + DB Orchestration)
│   │   └── analytics_service.py # Aggregation service (24h counts, referrers, user agents)
│   ├── schemas/
│   │   ├── url.py           # Request/Response data contracts
│   │   └── analytics.py     # Analytics aggregation schemas
│   └── routes/
│       ├── url.py           # Rate-limited and SSRF-protected route handlers
│       ├── analytics.py     # Aggregated analytics reporting routes
│       └── health.py        # /health/live and /health/ready diagnostic probes
├── docs/
│   └── architecture.md      # In-depth architectural design & capacity calculations
├── nginx/
│   └── nginx.conf           # Reverse proxy & load balancer configuration
├── tests/
│   ├── conftest.py          # Isolated test DB, fake Redis, and rate limiter fixtures
│   ├── test_circuit_breaker.py # Circuit breaker state transition tests
│   ├── test_observability.py# Tracing headers and health probes tests
│   ├── test_analytics.py    # AnalyticsWorker batching & aggregation query tests
│   ├── test_event_bus.py    # EventBus Producer-Consumer queue & backpressure tests
│   ├── test_cache.py        # Cache-Aside, TTL, and invalidation tests
│   ├── test_rate_limiter.py # Sliding window rate limiting & RFC headers tests
│   ├── test_security.py     # SSRF defense, private subnet, and loopback tests
│   ├── test_create_url.py   # POST /api/v1/shorten tests
│   ├── test_read_url.py     # GET endpoints tests
│   ├── test_delete_url.py   # DELETE endpoint tests
│   ├── test_redirect.py     # Redirect & click tracking tests
│   ├── test_validation.py   # Input validation & boundary tests
│   ├── test_url_repository.py # Repository unit tests
│   └── test_url_service.py    # Service domain rules tests
├── Dockerfile               # Multi-stage container build
├── docker-compose.yml       # Full-stack container orchestration
├── requirements.txt
└── .env                     # Environment config (gitignored)
```

---

## 📖 Deep-Dive Architecture Guide

For mathematical capacity estimations (QPS, RAM, 5-year storage projections) and failure mode mitigations, see [docs/architecture.md](docs/architecture.md).
