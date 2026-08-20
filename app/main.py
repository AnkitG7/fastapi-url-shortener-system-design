# ======================================================
# main.py — FastAPI Application Entry Point
# ======================================================
# SYSTEM DESIGN CONCEPT: Application Lifecycle & DB Init
# -------------------------------------------------
# On startup, we ensure database tables are initialized and
# connection pools are ready. On shutdown, we dispose of
# the engine and active connections gracefully.
# ======================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import engine
from app.db.models import Base
from app.routes.url import router as url_router, redirect_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes DB tables on startup and cleans up on shutdown.
    """
    settings = get_settings()
    print(f"[START] Starting {settings.app_name} v{settings.app_version}")
    print(f"[DOCS]  API docs available at {settings.base_url}/docs")
    print(f"[DEBUG] Debug mode: {settings.debug}")

    # SYSTEM DESIGN CONCEPT: Schema Bootstrap
    # In development/prototype mode, create tables if they don't exist.
    # In production, this is managed via Alembic migrations.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[DB]    Database tables verified / initialized successfully")
    except Exception as e:
        print(f"[DB]    Warning: Could not connect to database on startup: {e}")

    yield  # App is running and serving requests

    # Shutdown: gracefully close connection pool
    print(f"[STOP]  Shutting down {settings.app_name}...")
    await engine.dispose()
    print("[DB]    Database connection pool closed.")


settings = get_settings()

app = FastAPI(
    title="URL Shortener API",
    description="""
## 🔗 URL Shortener Service

A production-grade URL shortening service built with FastAPI,
demonstrating real-world system design patterns.

### Features
- **Shorten URLs** — Create short, memorable links backed by PostgreSQL
- **Custom codes** — Choose your own short code
- **Expiration** — Set links to auto-expire
- **Click tracking** — Atomic click counting in the database
- **Redirect** — Short URLs redirect to the original destination
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
