# 📂 Codebase Walkthrough & File-by-File Architecture Guide

This document maps out the entire codebase, explaining what every directory and file does, why it exists, and how data flows through the application.

---

## 1. Directory Structure

```
system_design/
├── alembic/                 # Database schema version control & migration scripts
├── app/
│   ├── main.py              # Application entrypoint & multi-resource lifecycle
│   ├── dependencies.py      # Dependency Injection providers (Auth, RateLimiter, DB, Cache)
│   ├── core/
│   │   ├── config.py        # 12-Factor app settings management (Pydantic Settings)
│   │   ├── logging_config.py# Structured JSON logging formatter with correlation IDs
│   │   └── security.py      # SSRF validation, private IP filtering, UserTier enum
│   ├── db/
│   │   ├── database.py      # Async SQLAlchemy engine, connection pooling, session factory
│   │   └── models.py        # ORM models (urls and clicks tables)
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
│   │   ├── url.py           # URL request/response data contracts
│   │   └── analytics.py     # Analytics aggregation schemas
│   └── routes/
│       ├── url.py           # Core URL shortener & redirect endpoints
│       ├── analytics.py     # Telemetry & aggregation reporting endpoints
│       └── health.py        # /health/live and /health/ready diagnostic probes
├── docs/
│   ├── 01_system_design_deep_dive.md       # Comprehensive concept guide
│   ├── 02_system_design_interview_prep.md   # Interview Q&A & estimation math
│   └── 03_codebase_walkthrough.md          # File-by-file code guide (this file)
├── nginx/
│   └── nginx.conf           # Reverse proxy & load balancer configuration
├── tests/                   # 79 automated unit, integration, and security tests
├── Dockerfile               # Multi-stage production container build
├── docker-compose.yml       # Full-stack container orchestration
├── requirements.txt         # Project dependencies
└── README.md                # Project documentation & quickstart
```

---

## 2. Request Lifecycle & Flow

### When a User Creates a Short URL (`POST /api/v1/shorten`):
```
1. Client sends JSON payload + optional X-API-Key header.
2. LoggingMiddleware assigns a unique X-Correlation-ID and starts timer.
3. enforce_rate_limit dependency validates user tier (Anonymous/Free/Premium)
   and checks Redis Sliding Window (ZSET).
4. validate_and_sanitize_url checks input against SSRF and private IP subnets.
5. URLService checks custom code uniqueness or generates a unique 7-char code.
6. URLRepository writes record to PostgreSQL via AsyncSession.
7. URLCache pre-warms Redis with the new key (Write-Through optimization).
8. Endpoint returns 201 Created with JSON URLResponse.
```

### When a User Visits a Short URL (`GET /{short_code}`):
```
1. Client requests http://localhost/k5ZgY6b.
2. Nginx Load Balancer routes request to an available FastAPI instance.
3. URLService queries URLCache (Redis):
   - [Cache Hit]: Returns destination URL in <1ms!
   - [Cache Miss]: Queries PostgreSQL via URLRepository -> Populates Redis.
4. Route publishes ClickEvent to EventBus queue (non-blocking).
5. Route immediately returns 307 Temporary Redirect to user's browser.
6. In the background:
   - AnalyticsWorker drains ClickEvents from EventBus.
   - Flushes events as a single bulk multi-row INSERT into PostgreSQL.
   - Atomically increments click_count on urls table.
```

---

## 3. How to Run & Verify Everything

```bash
# 1. Start full production stack
docker compose up -d

# 2. Run test suite (79 tests)
pytest tests/ -v

# 3. Test Liveness & Readiness Probes
curl http://localhost/health/live
curl http://localhost/health/ready

# 4. View OpenAPI Docs
# http://localhost/docs
```
