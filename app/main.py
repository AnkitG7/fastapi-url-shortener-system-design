# ======================================================
# main.py — FastAPI Application Entry Point
# ======================================================
# SYSTEM DESIGN CONCEPT: Application Lifecycle
# -------------------------------------------------
# This file is the "front door" of your application.
# It's responsible for:
#
# 1. CREATING the app instance
# 2. CONFIGURING middleware (logging, CORS, auth, etc.)
# 3. MOUNTING routers (URL routes, analytics, etc.)
# 4. DEFINING lifecycle events (startup/shutdown hooks)
#
# REAL-WORLD ANALOGY:
# Think of this as the reception desk of a hotel.
# It doesn't DO the work (that's the rooms/restaurant),
# but it DIRECTS everyone to the right place and handles
# cross-cutting concerns like security and check-in.
#
# SYSTEM DESIGN CONCEPT: Middleware Pipeline
# -------------------------------------------------
# Every request flows through middleware BEFORE reaching
# your route handler, and the response flows back through
# middleware AFTER your handler returns:
#
#   Request → [CORS] → [Logging] → [Auth] → [Rate Limit] → Handler
#   Response ← [CORS] ← [Logging] ← [Auth] ← [Rate Limit] ← Handler
#
# This is the CHAIN OF RESPONSIBILITY pattern.
# We'll add middleware in later phases.
# ======================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routes.url import router as url_router, redirect_router


# -------------------------------------------------------
# LIFECYCLE EVENTS — Startup & Shutdown
# -------------------------------------------------------
# SYSTEM DESIGN CONCEPT: Resource Management
# -------------------------------------------------
# In production systems, you need to:
# - STARTUP: Initialize DB connections, cache, workers
# - SHUTDOWN: Close connections gracefully, flush buffers
#
# WHY? Because:
# 1. Unclosed DB connections = connection pool exhaustion
# 2. Unflushed buffers = data loss
# 3. Unfinished background tasks = inconsistent state
#
# FastAPI uses the "lifespan" pattern for this.
# -------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Everything BEFORE `yield` runs at STARTUP.
    Everything AFTER `yield` runs at SHUTDOWN.

    Phase 2: We'll initialize DB connections here.
    Phase 3: We'll initialize Redis connections here.
    Phase 5: We'll start background workers here.
    """
    settings = get_settings()
    print(f"[START] Starting {settings.app_name} v{settings.app_version}")
    print(f"[DOCS]  API docs available at {settings.base_url}/docs")
    print(f"[DEBUG] Debug mode: {settings.debug}")

    yield  # App is running and serving requests

    # Shutdown
    print(f"[STOP]  Shutting down {settings.app_name}...")


# -------------------------------------------------------
# CREATE THE APP
# -------------------------------------------------------

settings = get_settings()

app = FastAPI(
    title="URL Shortener API",
    description="""
## 🔗 URL Shortener Service

A production-grade URL shortening service built with FastAPI,
demonstrating real-world system design patterns.

### Features
- **Shorten URLs** — Create short, memorable links
- **Custom codes** — Choose your own short code
- **Expiration** — Set links to auto-expire
- **Click tracking** — See how many times a link was clicked
- **Redirect** — Short URLs redirect to the original

### System Design Concepts
This project demonstrates: REST API design, caching, rate limiting,
async processing, observability, and more.
    """,
    version=settings.app_version,
    lifespan=lifespan,
    # These appear in Swagger UI
    docs_url="/docs",         # Swagger UI
    redoc_url="/redoc",       # ReDoc (alternative docs UI)
    openapi_url="/openapi.json",  # Raw OpenAPI spec
)


# -------------------------------------------------------
# MIDDLEWARE: CORS (Cross-Origin Resource Sharing)
# -------------------------------------------------------
# SYSTEM DESIGN CONCEPT: CORS
# -------------------------------------------------
# Browsers block requests from one domain to another
# (e.g., frontend on localhost:3000 calling API on
# localhost:8000). CORS headers tell the browser
# "it's OK, I allow requests from these origins."
#
# In production, you'd restrict this to your actual
# frontend domain(s). We allow all origins for dev.
# -------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # In production: ["https://yourdomain.com"]
    allow_credentials=True,
    allow_methods=["*"],        # Allow all HTTP methods
    allow_headers=["*"],        # Allow all headers
)


# -------------------------------------------------------
# MOUNT ROUTERS
# -------------------------------------------------------
# SYSTEM DESIGN CONCEPT: Modular Architecture
# -------------------------------------------------
# Each router handles a specific DOMAIN of the application.
# This is the same idea as MICROSERVICES at a smaller scale:
# each module is independent and has clear boundaries.
#
# If this were a microservices architecture, each router
# could be its own separate service. We start MONOLITHIC
# and split later — this is the recommended approach
# (even by microservices advocates like Martin Fowler).
# -------------------------------------------------------

# API routes (prefixed with /api/v1)
app.include_router(url_router)

# Redirect route (no prefix — short URLs like /{code})
# IMPORTANT: This must be LAST because /{short_code} is a
# catch-all pattern that would match ANY path. By including
# it last, the more specific routes (/api/v1/...) take priority.
app.include_router(redirect_router)


# -------------------------------------------------------
# ROOT ENDPOINT — API Information
# -------------------------------------------------------

@app.get(
    "/",
    summary="API Root",
    description="Returns basic API information and links.",
    tags=["Info"],
)
async def root():
    """
    Root endpoint — provides API information.

    SYSTEM DESIGN CONCEPT: API Discoverability
    ------------------------------------------
    A good API should be DISCOVERABLE. The root endpoint
    tells clients:
    1. What this API is
    2. Where to find documentation
    3. What version they're talking to

    This is inspired by the HATEOAS principle (Hypermedia
    As The Engine Of Application State) — though we keep
    it simple here.
    """
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": f"{settings.base_url}/docs",
        "health": f"{settings.base_url}/health",
        "endpoints": {
            "shorten": "POST /api/v1/shorten",
            "redirect": "GET /{short_code}",
            "details": "GET /api/v1/urls/{short_code}",
            "list": "GET /api/v1/urls",
            "delete": "DELETE /api/v1/urls/{short_code}",
        },
    }
