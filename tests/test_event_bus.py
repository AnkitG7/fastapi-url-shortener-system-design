# ======================================================
# tests/test_event_bus.py — Event Bus & Queue Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Producer-Consumer & Queue Testing
# -------------------------------------------------
# 1. Non-blocking publishing
# 2. Batch retrieval with timeouts
# 3. Bounded queue backpressure protection
# ======================================================

import asyncio
from datetime import datetime, timezone
import pytest

from app.events.event_bus import ClickEvent, EventBus


@pytest.mark.anyio
async def test_event_bus_publish_and_get_batch():
    """Test publishing multiple events and consuming them as a batch."""
    bus = EventBus(maxsize=100)

    # Publish 3 events
    for i in range(3):
        await bus.publish(
            ClickEvent(
                short_code=f"code_{i}",
                timestamp=datetime.now(timezone.utc),
                ip_address=f"192.0.2.{i}",
            )
        )

    assert bus.qsize() == 3

    # Drain batch
    batch = await bus.get_batch(max_batch_size=10, timeout_seconds=0.5)
    assert len(batch) == 3
    assert bus.qsize() == 0
    assert batch[0].short_code == "code_0"


@pytest.mark.anyio
async def test_event_bus_bounded_queue_drops_when_full():
    """
    SYSTEM DESIGN CONCEPT: Backpressure & Load Shedding
    --------------------------------------------------
    Verify that when the event queue is full, new events are
    dropped safely without crashing or leaking memory.
    """
    small_bus = EventBus(maxsize=2)

    # Fill queue
    assert await small_bus.publish(ClickEvent(short_code="1")) is True
    assert await small_bus.publish(ClickEvent(short_code="2")) is True

    # 3rd event should be dropped (returns False)
    assert await small_bus.publish(ClickEvent(short_code="3")) is False
