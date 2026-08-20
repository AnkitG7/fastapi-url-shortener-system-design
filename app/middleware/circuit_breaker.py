# ======================================================
# middleware/circuit_breaker.py — Circuit Breaker Pattern
# ======================================================
# SYSTEM DESIGN CONCEPT: Circuit Breaker Pattern & Cascading Failures
# -------------------------------------------------
# 1. WHAT IS A CIRCUIT BREAKER?
#    Inspired by electrical circuit breakers. When an external
#    service (e.g. Redis, Payment Gateway, External API) starts
#    failing, continuing to send requests will:
#    - Exhaust connection pools & threads
#    - Increase latency for all other requests
#    - Cause a CASCADING OUTAGE across the whole system
#
# 2. THREE STATES:
#    - CLOSED (Normal): Calls pass through. Failures are counted.
#    - OPEN (Tripped): Calls fail IMMEDIATELY with error (<0.1ms),
#      giving the failing dependency time to recover.
#    - HALF_OPEN (Trial): After a cooldown timeout, allows a few
#      probe requests. If they succeed, resets to CLOSED. If they
#      fail, trips back to OPEN.
# ======================================================

import asyncio
import time
import logging
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, name: str, retry_after_seconds: float):
        self.name = name
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Circuit breaker '{name}' is OPEN. Failing fast. Retry in {retry_after_seconds:.1f}s.")


class CircuitBreaker:
    """
    State machine implementing the Circuit Breaker pattern.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 10.0,
        half_open_success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.half_open_success_threshold = half_open_success_threshold

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_state_change: float = time.time()

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute an async function wrapped with circuit breaker protection.
        """
        now = time.time()

        # Check if OPEN state has cooled down -> transition to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.recovery_timeout:
                logger.info(f"[CIRCUIT BREAKER: {self.name}] Recovery timeout reached. Transitioning OPEN -> HALF_OPEN.")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                retry_in = self.recovery_timeout - (now - self.last_state_change)
                raise CircuitBreakerOpenError(self.name, retry_in)

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure(exc)
            raise exc

    def _on_success(self) -> None:
        """Handle successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_success_threshold:
                logger.info(f"[CIRCUIT BREAKER: {self.name}] Probe calls succeeded. Transitioning HALF_OPEN -> CLOSED.")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_state_change = time.time()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _on_failure(self, exc: Exception) -> None:
        """Handle execution failure."""
        self.failure_count += 1
        logger.warning(f"[CIRCUIT BREAKER: {self.name}] Failure #{self.failure_count}: {exc}")

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"[CIRCUIT BREAKER: {self.name}] Probe call failed. Tripping HALF_OPEN -> OPEN.")
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.error(f"[CIRCUIT BREAKER: {self.name}] Failure threshold reached ({self.failure_count}). Tripping CLOSED -> OPEN.")
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
