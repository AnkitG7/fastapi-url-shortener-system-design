# 🔗 FastAPI URL Shortener — System Design Learning Project

A **production-grade URL shortener** built with FastAPI, designed to teach **system design concepts** through hands-on code.

Every file is heavily commented with explanations of **WHY** things are done a certain way — not just how.

## 🎯 What You'll Learn

This project teaches **20+ system design concepts** across 7 phases:

| Phase | Concepts | Status |
|-------|----------|:------:|
| **1. API Design** | REST, Data Contracts, Pagination, HTTP Status Codes | ✅ Done |
| **2. Database Layer** | Schema Design, ORM, Repository Pattern, Migrations, Connection Pooling | ✅ Done |
| **3. Caching & Performance** | Redis, Cache-Aside Pattern, TTL, Cache Invalidation, Graceful Degradation | ✅ Done |
| **4. Auth, Rate Limiting & Security** | Sliding Window Log (Redis ZSET), Tiered API Keys, SSRF Prevention, HTTP 429 | ✅ Done |
| **5. Async Processing & Analytics** | Producer-Consumer Pattern, Event Bus, Background Batch Worker, CQRS Aggregations | ✅ Done |
| **6. Observability & Reliability** | Structured JSON Logging, Distributed Tracing (`X-Correlation-ID`), Health Probes, Circuit Breaker | ✅ Done |
| 7. Scaling & Deployment | Dockerfile, Multi-Replica Clustering, Nginx Load Balancer | Up Next |

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/AnkitG7/fastapi-url-shortener-system-design.git
cd fastapi-url-shortener-system-design

# Start PostgreSQL and Redis via Docker
docker compose up -d

# Setup Virtual Environment
python -m venv venv
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/Mac

pip install -r requirements.txt

# Run Database Migrations
alembic upgrade head

# Run Application
uvicorn app.main:app --reload --port 8000

# Open Swagger UI
# http://localhost:8000/docs
```

## 🧪 Run Tests

```bash
pytest tests/ -v
```

**79 tests** covering all endpoints, circuit breaker state machine, correlation ID tracing, health check probes, background worker batching, event bus queue backpressure, analytics aggregation, sliding window rate limits, SSRF security defenses, caching behaviors, database repository layer, service business logic, validation, and redirects.

## 📁 Project Structure

```
├── alembic/                 # Database migrations (schema version control)
│   ├── versions/            # Migration scripts
│   └── env.py               # Migration environment configuration
├── app/
│   ├── main.py              # FastAPI entry point, middleware, multi-resource & worker lifecycle
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
│   │   └── url_service.py   # Business Logic Layer (Cache-Aside + DB Orchestration)
│   │   └── analytics_service.py # Aggregation service (24h counts, referrers, user agents)
│   ├── schemas/
│   │   ├── url.py           # Request/Response data contracts
│   │   └── analytics.py     # Analytics aggregation schemas
│   └── routes/
│       ├── url.py           # Rate-limited and SSRF-protected route handlers
│       ├── analytics.py     # Aggregated analytics reporting routes
│       └── health.py        # /health/live and /health/ready diagnostic probes
├── tests/
│   ├── conftest.py          # Isolated test DB, fake Redis, and rate limiter fixtures
│   ├── test_observability.py# Tracing headers and health probes tests
│   ├── test_circuit_breaker.py # Circuit breaker state transition tests
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
├── docker-compose.yml       # Infrastructure as Code (PostgreSQL + Redis)
├── requirements.txt
└── .env                     # Environment config (gitignored)
```

## 📖 System Design Concepts in Phase 6

- **Structured JSON Logging** — Machine-readable logs containing timestamps, log levels, correlation IDs, and millisecond latencies for central ingestion in Datadog / Grafana Loki / ELK.
- **Distributed Tracing & Correlation IDs** — Propagating `X-Correlation-ID` across HTTP headers, background workers, and logs to trace individual user requests across microservices.
- **Liveness Probes (`/health/live`)** — Allows container orchestrators (Docker/Kubernetes) to detect deadlocked or hung processes and automatically restart them.
- **Readiness Probes (`/health/ready`)** — Verifies PostgreSQL and Redis dependencies and latencies; load balancers automatically stop routing traffic to unhealthy instances.
- **Circuit Breaker Pattern** — Prevents cascading system failures when downstream services fail by failing fast (`OPEN` state) and automatically recovering (`HALF_OPEN` -> `CLOSED`).
