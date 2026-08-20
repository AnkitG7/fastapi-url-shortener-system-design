# 🔗 FastAPI URL Shortener — System Design Learning Project

A **production-grade URL shortener** built with FastAPI, designed to teach **system design concepts** through hands-on code.

Every file is heavily commented with explanations of **WHY** things are done a certain way — not just how.

## 🎯 What You'll Learn

This project teaches **20+ system design concepts** across 7 phases:

| Phase | Concepts |
|-------|----------|
| **1. API Design (current)** | REST, Data Contracts, Pagination, HTTP Status Codes |
| 2. Database Layer | Schema Design, ORM, Repository Pattern, Migrations |
| 3. Caching | Redis, Cache-Aside, TTL, Cache Invalidation |
| 4. Auth & Rate Limiting | API Keys, Token Bucket, Middleware |
| 5. Async Processing | Background Workers, Event-Driven Architecture |
| 6. Observability | Structured Logging, Health Checks, Circuit Breakers |
| 7. Scaling | Docker, Load Balancing, Horizontal Scaling |

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/AnkitG7/fastapi-url-shortener-system-design.git
cd fastapi-url-shortener-system-design

# Setup
python -m venv venv
.\venv\Scripts\activate       # Windows
# source venv/bin/activate    # Linux/Mac

pip install -r requirements.txt

# Run
uvicorn app.main:app --reload --port 8000

# Open Swagger UI
# http://localhost:8000/docs
```

## 🧪 Run Tests

```bash
pytest tests/ -v
```

**46 tests** covering all endpoints, validation, redirects, and edge cases.

## 📁 Project Structure

```
├── app/
│   ├── main.py              # FastAPI entry point, middleware, lifecycle
│   ├── core/
│   │   └── config.py        # Type-safe configuration (Pydantic Settings)
│   ├── schemas/
│   │   └── url.py           # Request/Response data contracts
│   └── routes/
│       └── url.py           # URL shortener CRUD + redirect endpoints
├── tests/
│   ├── conftest.py          # Shared fixtures & test setup
│   ├── test_create_url.py   # POST /api/v1/shorten tests
│   ├── test_read_url.py     # GET endpoints tests
│   ├── test_delete_url.py   # DELETE endpoint tests
│   ├── test_redirect.py     # Redirect & click tracking tests
│   └── test_validation.py   # Input validation & boundary tests
├── requirements.txt
└── .env                     # Environment config (gitignored)
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/shorten` | Create a short URL |
| `GET` | `/{short_code}` | Redirect to original URL (307) |
| `GET` | `/api/v1/urls/{short_code}` | Get URL details & stats |
| `GET` | `/api/v1/urls` | List all URLs (paginated) |
| `DELETE` | `/api/v1/urls/{short_code}` | Delete a URL |

## 📖 System Design Concepts in Phase 1

- **REST API Design** — Correct HTTP verbs, status codes, resource-based URLs
- **Data Contracts** — Pydantic models for input validation & output serialization
- **12-Factor App Config** — Environment-based configuration
- **Singleton Pattern** — `@lru_cache` for settings
- **ID Generation** — ShortUUID for short, unique, non-sequential codes
- **Pagination** — Offset-based with enforced limits
- **301 vs 307 Redirects** — Tradeoff between caching and analytics
- **Information Hiding** — Public short codes, not internal database IDs
- **CORS** — Cross-origin request handling
- **Test Isolation** — Clean state per test, fixtures for reusable setup

---

*Built as a learning project — read the code comments for deep-dive explanations!*
