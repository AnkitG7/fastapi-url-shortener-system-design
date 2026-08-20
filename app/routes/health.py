# ======================================================
# routes/health.py — Health Check Probes (Liveness & Readiness)
# ======================================================
# SYSTEM DESIGN CONCEPT: Health Probes for Orchestrators & Load Balancers
# -------------------------------------------------
# 1. LIVENESS PROBE (`/health/live`):
#    - Answers: "Is this process running or deadlocked?"
#    - If this returns non-200, Kubernetes/Docker restarts the container.
#
# 2. READINESS PROBE (`/health/ready`):
#    - Answers: "Can this instance handle user traffic right now?"
#    - Checks all critical backing services (PostgreSQL, Redis).
#    - If this returns 503, the Load Balancer (Nginx/HAProxy/AWS ALB)
#      stops sending traffic to this instance until it recovers.
# ======================================================

import time
from typing import Any, Dict
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.cache.redis_client import get_redis_client
from app.db.database import async_session_factory

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get(
    "",
    summary="General Health Check",
    description="Returns basic liveness status.",
)
@router.get(
    "/live",
    summary="Liveness Probe",
    description="Container orchestration probe to verify the process is alive.",
)
async def liveness():
    """Liveness probe: verifies the application server process is running."""
    return {"status": "alive"}


@router.get(
    "/ready",
    summary="Readiness Probe",
    description="Checks connectivity and response time for PostgreSQL and Redis.",
    responses={
        200: {"description": "All backing services are healthy and ready to serve traffic"},
        503: {"description": "One or more critical services are unavailable"},
    },
)
async def readiness(response: Response):
    """
    Readiness probe: validates database and cache dependencies with latencies.
    """
    components: Dict[str, Any] = {}
    is_ready = True

    # 1. Check PostgreSQL
    t0 = time.perf_counter()
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_latency = (time.perf_counter() - t0) * 1000
        components["postgres"] = {
            "status": "up",
            "latency_ms": round(db_latency, 2),
        }
    except Exception as e:
        is_ready = False
        components["postgres"] = {
            "status": "down",
            "error": str(e),
        }

    # 2. Check Redis
    t0 = time.perf_counter()
    try:
        client = get_redis_client()
        redis_ok = await client.ping()
        redis_latency = (time.perf_counter() - t0) * 1000
        if redis_ok:
            components["redis"] = {
                "status": "up",
                "latency_ms": round(redis_latency, 2),
            }
        else:
            components["redis"] = {"status": "down", "error": "Ping returned False"}
    except Exception as e:
        # Note: Redis is an optimization cache, but we flag it in readiness
        components["redis"] = {
            "status": "down",
            "error": str(e),
        }

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "components": components,
        }

    return {
        "status": "ready",
        "components": components,
    }
