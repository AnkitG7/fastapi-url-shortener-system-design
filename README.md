# 🔗 FastAPI URL Shortener — System Design Learning Project

A **production-grade URL shortener** built with FastAPI, designed to teach **system design concepts** through hands-on code.

Every file is heavily commented with explanations of **WHY** things are done a certain way — not just how.

## 🎯 What You'll Learn

This project teaches **20+ system design concepts** across 7 phases:

| Phase | Concepts | Status |
|-------|----------|:------:|
| **1. API Design** | REST, Data Contracts, Pagination, HTTP Status Codes | ✅ Done |
| **2. Database Layer** | Schema Design, ORM, Repository Pattern, Migrations, Connection Pooling | ✅ Done |
| 3. Caching | Redis, Cache-Aside, TTL, Cache Invalidation | Up Next |
| 4. Auth & Rate Limiting | API Keys, Token Bucket, Middleware | Planned |
| 5. Async Processing | Background Workers, Event-Driven Architecture | Planned |
| 6. Observability | Structured Logging, Health Checks, Circuit Breakers | Planned |
| 7. Scaling | Docker, Load Balancing, Horizontal Scaling | Planned |

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/AnkitG7/fastapi-url-shortener-system-design.git
cd fastapi-url-shortener-system-design

# Start Database via Docker
docker compose up -d postgres

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

**51 tests** covering all endpoints, database repository layer, service business logic, validation, redirects, and edge cases.

## 📁 Project Structure

```
├── alembic/                 # Database migrations (schema version control)
│   ├── versions/            # Migration scripts
│   └── env.py               # Migration environment configuration
├── app/
│   ├── main.py              # FastAPI entry point, middleware, lifecycle
│   ├── dependencies.py      # Dependency injection providers
│   ├── core/
│   │   └── config.py        # Type-safe configuration (Pydantic Settings)
│   ├── db/
│   │   ├── database.py      # Async engine, connection pooling, session factory
│   │   └── models.py        # SQLAlchemy ORM models (indexes, constraints)
│   ├── repositories/
│   │   └── url_repository.py# Data Access Layer (Atomic updates, CRUD)
│   ├── services/
│   │   └── url_service.py   # Business Logic Layer (Domain rules & exceptions)
│   ├── schemas/
│   │   └── url.py           # Request/Response data contracts
│   └── routes/
│       └── url.py           # Clean Architecture route handlers
├── tests/
│   ├── conftest.py          # Isolated test DB fixtures & overrides
│   ├── test_create_url.py   # POST /api/v1/shorten tests
│   ├── test_read_url.py     # GET endpoints tests
│   ├── test_delete_url.py   # DELETE endpoint tests
│   ├── test_redirect.py     # Redirect & click tracking tests
│   ├── test_validation.py   # Input validation & boundary tests
│   ├── test_url_repository.py # Repository unit tests
│   └── test_url_service.py    # Service domain rules tests
├── docker-compose.yml       # Infrastructure as Code (PostgreSQL)
├── requirements.txt
└── .env                     # Environment config (gitignored)
```

## 📖 System Design Concepts in Phase 2

- **Relational Schema Design** — Normalization, server-side timestamps (`func.now()`), constraints.
- **Database Indexing** — B-tree index on `short_code` ($O(\log n)$ vs $O(n)$ full table scans) and `created_at`.
- **Connection Pooling** — Reusing persistent connections to avoid expensive TCP/auth handshakes per query.
- **Async I/O** — Non-blocking database calls enabling high concurrency.
- **Repository Pattern** — Decoupling SQL queries and persistence from business rules.
- **Clean Architecture & Service Layer** — Transport-agnostic domain logic with custom Domain Exceptions.
- **Atomic Database Updates** — Avoiding concurrency race conditions during click counts via `click_count = click_count + 1`.
- **Database Migrations (Alembic)** — Schema version control and automated migration history.
- **Test Database Isolation** — Dependency overriding with in-memory async SQLite for fast and deterministic test runs.
