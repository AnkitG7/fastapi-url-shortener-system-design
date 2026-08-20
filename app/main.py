# ======================================================
# main.py — FastAPI Application Entry Point
# ======================================================
# SYSTEM DESIGN CONCEPT: Multi-Resource Lifecycle Management
# -------------------------------------------------
# We manage the lifecycle for both PostgreSQL and Redis:
# - Startup: Check DB & Redis connectivity, bootstrap tables
# - Shutdown: Close DB connection pool and Redis connection pool
# ======================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache.redis_client import check_redis_health, close_redis_pool
from app.core.config import get_settings
from app.db.database import engine
from app.db.models import Base
from app.routes.url import router as url_router, redirect_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes PostgreSQL and Redis connections on startup, cleans up on shutdown.
    """
    settings = get_settings()
    print(f"[START] Starting {settings.app_name} v{settings.app_version}")
    print(f"[DOCS]  API docs available at {settings.base_url}/docs")
    print(f"[DEBUG] Debug mode: {settings.debug}")

    # 1. Initialize PostgreSQL
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB]    PostgreSQL tables verified / initialized successfully")
    except Exception as e:
        print(f"[DB]    Warning: Could not connect to PostgreSQL on startup: {e}")

    # 2. Check Redis Health
    redis_healthy = await check_redis_health()
    if redis_healthy:
        print("[REDIS] Connected to Redis successfully (Cache-Aside ready)")
    else:
        print("[REDIS] Warning: Redis is not reachable. Falling back to DB-only mode.")

    yield  # App is serving traffic

    # Shutdown: gracefully close DB and Redis connection pools
    print(f"[STOP]  Shutting down {settings.app_name}...")
    await engine.dispose()
    print("[DB]    PostgreSQL connection pool closed.")
    await close_redis_pool()


settings = get_settings()

app = FastAPI(
    title="URL Shortener API",
    description="""
## 🔗 URL Shortener Service

A production-grade URL shortening service built with FastAPI, PostgreSQL, and Redis.

### Features
- **Shorten URLs** — High-performance link creation
- **Redis Cache-Aside** — Sub-millisecond URL lookups and redirects
- **Durable Storage** — PostgreSQL persistence with connection pooling
- **Atomic Click Tracking** — Concurrency-safe analytics
- **Alembic Migrations** — Database schema version control
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(url_router)
app.include_router(redirect_router)


@app.get(
    "/",
    summary="API Root",
    description="Returns basic API information and links.",
    tags=["Info"],
)
async def root():
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": f"{settings.base_url}/docs",
        "endpoints": {
            "shorten": "POST /api/v1/shorten",
            "redirect": "GET /{short_code}",
            "details": "GET /api/v1/urls/{short_code}",
            "list": "GET /api/v1/urls",
            "delete": "DELETE /api/v1/urls/{short_code}",
        },
    }
