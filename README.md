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
| 5. Async Processing | Background Workers, Event-Driven Architecture | Up Next |
| 6. Observability | Structured Logging, Health Checks, Circuit Breakers | Planned |
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

**67 tests** covering all endpoints, sliding window rate limits, SSRF security defenses, caching behaviors, database repository layer, service business logic, validation, and redirects.

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
│   │   └── security.py      # SSRF defense, private IP filtering, UserTier enum
│   ├── db/
│   │   ├── database.py      # Async engine, connection pooling, session factory
│   │   └── models.py        # SQLAlchemy ORM models (indexes, constraints)
│   ├── cache/
│   │   ├── redis_client.py  # Async Redis client, connection pooling, health checks
│   │   └── url_cache.py     # Cache-Aside pattern, TTL, namespacing, graceful degradation
│   ├── middleware/
│   │   ├── auth.py          # API key authentication & tier resolution
│   │   └── rate_limiter.py  # Redis Sliding Window Log rate limiter via Sorted Sets
│   ├── repositories/
│   │   └── url_repository.py# Data Access Layer (Atomic updates, CRUD)
│   ├── services/
│   │   └── url_service.py   # Business Logic Layer (Cache-Aside + DB Orchestration)
│   ├── schemas/
│   │   └── url.py           # Request/Response data contracts
│   └── routes/
│       └── url.py           # Rate-limited and SSRF-protected route handlers
├── tests/
│   ├── conftest.py          # Isolated test DB, fake Redis, and rate limiter fixtures
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

## 📖 System Design Concepts in Phase 4

- **Sliding Window Log Algorithm** — Implemented using Redis Sorted Sets (`ZSET`) with `ZREMRANGEBYSCORE`, `ZCARD`, and `ZADD` to eliminate the "boundary burst" flaw of Fixed Window counters.
- **Tiered Quality of Service (QoS)** — Differentiating limits for `Anonymous` (10 req/min), `Free` (100 req/min), and `Premium` (1000 req/min) user tiers.
- **Standard RFC Rate Limiting Headers** — Providing clients with `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After` on HTTP `429 Too Many Requests`.
- **SSRF (Server-Side Request Forgery) Defense** — Blocking requests to internal loopback (`127.0.0.1`, `localhost`), private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), and Cloud Metadata endpoints (`169.254.169.254`).
- **Fail-Open Strategy** — If Redis rate limiter is temporarily unavailable, the system defaults to allowing traffic rather than creating an outage for legitimate users.
