# ======================================================
# middleware/logging_middleware.py — Request Tracing & Latency Logging
# ======================================================
# SYSTEM DESIGN CONCEPT: Distributed Tracing & Correlation IDs
# -------------------------------------------------
# 1. WHAT IS A CORRELATION ID?
#    A unique identifier assigned to an HTTP request that
#    travels with that request across all microservices,
#    background workers, and log records.
#
# 2. BENEFITS:
#    - When an issue occurs, you can search for ONE ID in your
#      log aggregator and see the entire request lifecycle.
#    - Returned to the client in `X-Correlation-ID` so users
#      can provide it when reporting bugs.
#
# 3. LATENCY MONITORING:
#    Tracks exact execution time in milliseconds (`latency_ms`)
#    to detect slow endpoints and performance regressions.
# ======================================================

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import correlation_id_ctx

logger = logging.getLogger("http_access")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that attaches Correlation IDs and emits structured access logs.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Extract or generate Correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        correlation_id_ctx.set(correlation_id)

        start_time = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"HTTP {request.method} {request.url.path} failed with unhandled exception: {exc}",
                exc_info=True,
                extra={"extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "latency_ms": round(duration_ms, 2),
                    "client_ip": request.client.host if request.client else "-",
                }},
            )
            raise exc

        duration_ms = (time.perf_counter() - start_time) * 1000

        # 2. Attach Correlation ID to outgoing response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # 3. Emit structured access log
        extra_info = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else "-",
        }
        
        # Add extra fields to log record
        log_record = logger.makeRecord(
            logger.name,
            logging.INFO,
            "(unknown)",
            0,
            f"HTTP {request.method} {request.url.path} -> {response.status_code} ({duration_ms:.2f}ms)",
            (),
            None,
        )
        log_record.extra_fields = extra_info
        logger.handle(log_record)

        return response
