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
| 4. Auth & Rate Limiting | API Keys, Token Bucket, Sliding Window, Middleware | Up Next |
| 5. Async Processing | Background Workers, Event-Driven Architecture | Planned |
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

**56 tests** covering all endpoints, caching behaviors, database repository layer, service business logic, validation, redirects, and edge cases.

## 📁 Project Structure

```
├── alembic/                 # Database migrations (schema version control)
│   ├── versions/            # Migration scripts
│   └── env.py               # Migration environment configuration
├── app/
│   ├── main.py              # FastAPI entry point, middleware, multi-resource lifecycle
│   ├── dependencies.py      # Dependency injection providers (DB, Cache, Repo, Service)
│   ├── core/
│   │   └── config.py        # Type-safe configuration (Pydantic Settings)
│   ├── db/
│   │   ├── database.py      # Async engine, connection pooling, session factory
│   │   └── models.py        # SQLAlchemy ORM models (indexes, constraints)
│   ├── cache/
│   │   ├── redis_client.py  # Async Redis client, connection pooling, health checks
│   │   └── url_cache.py     # Cache-Aside pattern, TTL, namespacing, graceful degradation
│   ├── repositories/
│   │   └── url_repository.py# Data Access Layer (Atomic updates, CRUD)
│   ├── services/
│   │   └── url_service.py   # Business Logic Layer (Cache-Aside + DB Orchestration)
│   ├── schemas/
│   │   └── url.py           # Request/Response data contracts
│   └── routes/
│       └── url.py           # Clean Architecture route handlers
├── tests/
│   ├── conftest.py          # Isolated test DB & fake Redis fixtures
│   ├── test_cache.py        # Cache-Aside, TTL, and invalidation tests
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

## 📖 System Design Concepts in Phase 3

- **Cache-Aside (Lazy Loading)** — Reading from in-memory cache first; querying DB on cache miss and populating cache.
- **Write-Through / Pre-Warming** — Populating cache immediately upon resource creation.
- **Cache Invalidation** — Deleting cached keys when underlying DB records are deleted or expired.
- **TTL (Time to Live)** — Enforcing expiration on cached keys to prevent stale data and Redis memory overflow.
- **Graceful Degradation** — If Redis fails or goes offline, the application seamlessly falls back to PostgreSQL without crashing.
- **Key Namespacing** — Using hierarchical prefixes like `url:{short_code}` to prevent collisions in shared cache instances.
