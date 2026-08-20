# ======================================================
# db/database.py — Database Engine & Session Management
# ======================================================
# SYSTEM DESIGN CONCEPT: Connection Pooling
# -------------------------------------------------
# Opening a database connection is EXPENSIVE:
# 1. TCP handshake (network round-trip)
# 2. Authentication (verify credentials)
# 3. Session setup (allocate memory on DB server)
#
# Doing this for EVERY request would be disastrous at scale.
# Instead, we use a CONNECTION POOL:
#
#   App starts → Create N connections → Keep them OPEN
#   Request comes → BORROW a connection from pool
#   Request done → RETURN connection to pool (don't close!)
#
# This is like a car rental service:
# - Pool = the parking lot of pre-rented cars
# - Borrowing = taking a car for your trip
# - Returning = parking it back for the next person
# - No one buys/sells a car per trip (too expensive!)
#
# POOL SIZING (critical for production):
# - Too few connections → Requests queue up → Slow responses
# - Too many connections → DB overwhelmed → Everything crashes
# - Rule of thumb: pool_size = (2 * CPU_cores) + num_disks
#   For a typical server: 5-20 connections per app instance
#
# SYSTEM DESIGN CONCEPT: Async I/O
# -------------------------------------------------
# We use ASYNC SQLAlchemy because database queries involve
# WAITING (for network, for disk I/O). During that wait,
# an async server can handle OTHER requests instead of
# blocking. This is why async matters:
#
# Sync:  Request1[====WAIT====]  Request2[====WAIT====]
# Async: Request1[====WAIT====]
#        Request2[====WAIT====]  ← Handled DURING wait!
#
# With 100 concurrent users, sync needs 100 threads.
# Async handles them all on a SINGLE thread.
# ======================================================

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# -------------------------------------------------------
# CREATE THE ASYNC ENGINE
# -------------------------------------------------------
# The engine is the ENTRY POINT to the database.
# It manages the connection pool and dialect (PostgreSQL).
# -------------------------------------------------------

engine = create_async_engine(
    settings.database_url,

    # --- Connection Pool Settings ---
    # SYSTEM DESIGN CONCEPT: Pool Configuration
    pool_size=5,          # Keep 5 connections always open
    max_overflow=10,      # Allow up to 10 MORE under heavy load
    pool_timeout=30,      # Wait max 30s for a connection, then error
    pool_recycle=1800,    # Recycle connections after 30 min
                          # (prevents stale connections after DB restart)
    pool_pre_ping=True,   # Test connection health before using it
                          # (slightly slower, but prevents "connection closed" errors)

    # --- Debug ---
    echo=settings.debug,  # Log all SQL queries when debug=True
                          # NEVER enable in production (performance + security)
)


# -------------------------------------------------------
# CREATE THE SESSION FACTORY
# -------------------------------------------------------
# SYSTEM DESIGN CONCEPT: Factory Pattern
# -------------------------------------------------
# A session factory creates Session objects. We configure
# it ONCE and use it everywhere. This ensures all sessions
# have the same settings (expire_on_commit, etc.)
#
# Session lifecycle per request:
# 1. Create session (borrow connection from pool)
# 2. Execute queries
# 3. Commit or rollback
# 4. Close session (return connection to pool)
#
# CRITICAL: Sessions are NOT thread-safe. Each request
# MUST get its own session. That's why we use a factory
# (creates new session per request) instead of a global session.
# -------------------------------------------------------

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    # WHY expire_on_commit=False?
    # By default, after commit(), SQLAlchemy marks all loaded
    # objects as "expired" — accessing any attribute triggers
    # a NEW query. This is wasteful when you just want to
    # return the data you already have. Setting this to False
    # means "trust the data I already loaded."
)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency that provides a database session.

    SYSTEM DESIGN CONCEPT: Dependency Injection (DI)
    ------------------------------------------------
    Instead of creating sessions inside route handlers,
    we INJECT them. This is powerful because:

    1. TESTABILITY — In tests, we inject a TEST database session
       (pointing to a test DB) instead of the real one.

    2. LIFECYCLE MANAGEMENT — The `async with` block guarantees
       the session is closed even if the handler crashes.
       This prevents CONNECTION LEAKS (borrowed connections
       never returned to the pool = pool exhaustion = app dies).

    3. SEPARATION OF CONCERNS — Route handlers don't know
       (or care) HOW sessions are created. They just use them.

    Usage in route handlers:
        @router.get("/urls")
        async def list_urls(db: AsyncSession = Depends(get_db)):
            ...

    The `Depends(get_db)` tells FastAPI:
    "Call get_db(), give me the result, and clean up after."
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
