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
| 6. Observability & Reliability | Structured Logging, Health Checks, Circuit Breakers | Up Next |
| 7. Scaling | Docker, Load Balancing, Horizontal Scaling | Planned |

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

**72 tests** covering all endpoints, background worker batching, event bus queue backpressure, analytics aggregation, sliding window rate limits, SSRF security defenses, caching behaviors, database repository layer, service business logic, validation, and redirects.

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
│   │   └── rate_limiter.py  # Redis Sliding Window Log rate limiter via Sorted Sets
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
│       └── analytics.py     # Aggregated analytics reporting routes
├── tests/
│   ├── conftest.py          # Isolated test DB, fake Redis, and rate limiter fixtures
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

## 📖 System Design Concepts in Phase 5

- **Non-Blocking Hot Path** — Decoupling redirect execution from analytics telemetry so users experience $<1\text{ms}$ redirect latency without waiting on database write operations.
- **Producer-Consumer Pattern** — Redirect requests produce `ClickEvent` messages to an asynchronous queue; a background worker consumes and drains them.
- **Batch / Bulk Writes** — Grouping individual click events into single multi-row `INSERT` statements to reduce database I/O round-trips by $50\times-100\times$.
- **Bounded Queue & Backpressure** — Setting a capacity limit on the queue prevents server memory exhaustion during massive traffic surges.
- **Graceful Worker Drain** — Ensuring any pending events in the queue are completely flushed to PostgreSQL on application shutdown to guarantee zero data loss.
- **CQRS (Command Query Responsibility Segregation)** — Separating high-velocity write paths (asynchronous event ingestion) from analytical read paths (aggregate SQL queries).
