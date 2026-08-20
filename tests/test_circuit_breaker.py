# ======================================================
# tests/test_circuit_breaker.py — Circuit Breaker Pattern Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Fault Tolerance & Circuit Breaker Verification
# -------------------------------------------------
# 1. Normal execution in CLOSED state
# 2. Tripping to OPEN state after consecutive failures
# 3. Failing fast in OPEN state
# 4. Recovering via HALF_OPEN state to CLOSED
# ======================================================

import asyncio
import pytest
from app.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


@pytest.mark.anyio
async def test_circuit_breaker_normal_execution():
    """Test successful function execution in CLOSED state."""
    breaker = CircuitBreaker(name="test_service", failure_threshold=3)

    async def successful_call():
        return "success"

    result = await breaker.call(successful_call)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0


@pytest.mark.anyio
async def test_circuit_breaker_trips_to_open_after_failures():
    """
    Test consecutive failures trip the breaker to OPEN state.
    """
    breaker = CircuitBreaker(name="failing_service", failure_threshold=2, recovery_timeout_seconds=0.5)

    async def failing_call():
        raise RuntimeError("Service unavailable")

    # Failure 1
    with pytest.raises(RuntimeError):
        await breaker.call(failing_call)
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 1

    # Failure 2 -> Trips to OPEN
    with pytest.raises(RuntimeError):
        await breaker.call(failing_call)
    assert breaker.state == CircuitState.OPEN

    # 3rd call must fail immediately with CircuitBreakerOpenError without invoking failing_call
    with pytest.raises(CircuitBreakerOpenError) as exc:
        await breaker.call(failing_call)
    assert "is OPEN" in str(exc.value)


@pytest.mark.anyio
async def test_circuit_breaker_recovers_to_closed():
    """
    Test that after recovery timeout, the breaker transitions to HALF_OPEN and then CLOSED on success.
    """
    breaker = CircuitBreaker(
        name="recovering_service",
        failure_threshold=1,
        recovery_timeout_seconds=0.2,
        half_open_success_threshold=1,
    )

    should_fail = True

    async def dynamic_service():
        if should_fail:
            raise ConnectionError("Network down")
        return "recovered"

    # Trip to OPEN
    with pytest.raises(ConnectionError):
        await breaker.call(dynamic_service)
    assert breaker.state == CircuitState.OPEN

    # Wait for recovery timeout
    await asyncio.sleep(0.25)

    # Service recovers
    should_fail = False

    # Next call probe succeeds -> resets to CLOSED
    result = await breaker.call(dynamic_service)
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
