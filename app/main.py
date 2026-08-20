# ======================================================
# main.py — FastAPI Application Entry Point (with Background Workers)
# ======================================================
# SYSTEM DESIGN CONCEPT: Multi-Resource Lifecycle & Background Worker Management
# -------------------------------------------------
# Lifespan:
# 1. Startup: Init PostgreSQL, check Redis, start AnalyticsWorker loop
# 2. Shutdown: Gracefully drain worker queue, close Redis & DB pools
# ======================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.cache.redis_client import check_redis_health, close_redis_pool
from app.core.config import get_settings
from app.db.database import engine
from app.db.models import Base
from app.routes.analytics import router as analytics_router
from app.routes.url import redirect_router, router as url_router
from app.workers.analytics_worker import get_analytics_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
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

    # 3. Start Background Analytics Worker
    worker = get_analytics_worker()
    worker.start()
    print("[WORKER] Background analytics batch worker started.")

    yield  # App is serving traffic

    # Shutdown: gracefully drain background workers and close pools
    print(f"[STOP]  Shutting down {settings.app_name}...")
    await worker.stop()
    print("[WORKER] Background worker drained and stopped.")
    await engine.dispose()
    print("[DB]    PostgreSQL connection pool closed.")
    await close_redis_pool()


settings = get_settings()

app = FastAPI(
    title="URL Shortener API",
    description="""
## 🔗 URL Shortener Service

A production-grade URL shortening service built with FastAPI, PostgreSQL, Redis, and Async Background Workers.

### Features
- **Shorten URLs** — High-performance link creation
- **Redis Cache-Aside** — Sub-millisecond URL lookups and redirects
- **Sliding Window Rate Limiting** — Redis Sorted Sets rate limiter
- **SSRF Defense** — Private IP and cloud metadata protection
- **Async Event-Driven Telemetry** — Producer-Consumer pattern with batch database writes
- **Analytics Reporting** — Aggregated click telemetry & referrer breakdowns
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
app.include_router(analytics_router)
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
            "analytics": "GET /api/v1/urls/{short_code}/analytics",
            "list": "GET /api/v1/urls",
            "delete": "DELETE /api/v1/urls/{short_code}",
        },
    }
