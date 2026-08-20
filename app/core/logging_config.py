# ======================================================
# core/logging_config.py — Structured JSON Logging
# ======================================================
# SYSTEM DESIGN CONCEPT: Structured Logging & Distributed Tracing
# -------------------------------------------------
# 1. WHY STRUCTURED JSON LOGS?
#    - Traditional text logs (`print("User clicked link")`) are
#      hard to index and query in production log aggregators
#      (Datadog, ELK Stack, Grafana Loki, CloudWatch).
#    - JSON logs allow searching by specific fields:
#      `correlation_id = "abc"` or `latency_ms > 500` or `status = 500`.
#
# 2. CONTEXT & CORRELATION IDS:
#    - Context variables (`contextvars`) propagate `correlation_id`
#      across async tasks without having to pass it through every function.
# ======================================================

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict

# Context variable to hold the correlation ID for the current request
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs log records as structured JSON strings.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get() or "-",
        }

        # Include exception details if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include any custom extra attributes passed to the logger
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(debug: bool = False) -> None:
    """Configure root logger with the structured JSON formatter."""
    level = logging.DEBUG if debug else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Replace existing handlers to avoid duplicate text output
    root_logger.handlers = [handler]

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
