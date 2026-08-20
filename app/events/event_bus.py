# ======================================================
# events/event_bus.py — Async In-Memory Event Bus
# ======================================================
# SYSTEM DESIGN CONCEPT: Producer-Consumer Pattern & Event-Driven Architecture
# -------------------------------------------------
# 1. DECOUPLING:
#    The HTTP Redirect route (PRODUCER) should NOT wait for:
#    - Geolocation IP lookup
#    - User-agent parsing
#    - Inserting rows into PostgreSQL
#
# 2. PRODUCER-CONSUMER FLOW:
#    User Clicks -> Route pushes ClickEvent to Queue -> 307 Redirects immediately (<1ms)
#                                    |
#                          [Event Bus / Queue]
#                                    |
#                    Background Worker (CONSUMER)
#                                    |
#                       Batch DB Insert (1 query)
#
# 3. BACKPRESSURE & BUFFERING:
#    The `asyncio.Queue` acts as a shock absorber during traffic spikes.
#    Even if 10,000 users click at once, the database is protected
#    because the worker processes them in controlled batches.
#
# In a distributed multi-instance architecture (Phase 7), this in-memory
# queue can be swapped for Redis Streams, Kafka, or RabbitMQ.
# ======================================================

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClickEvent:
    """Telemetry payload produced when a short URL is clicked."""
    short_code: str
    url_id: Optional[int] = None
    timestamp: datetime = datetime.now(timezone.utc)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None


class EventBus:
    """
    Asynchronous event bus implementing the Producer-Consumer pattern.
    """

    def __init__(self, maxsize: int = 10000):
        # Bounded queue prevents unbounded memory growth during extreme load
        self._queue: asyncio.Queue[ClickEvent] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, event: ClickEvent) -> bool:
        """
        Publish an event to the queue (non-blocking).
        Returns True if queued, False if queue is full (backpressure drop).
        """
        try:
            self._queue.put_nowait(event)
            return True
        except asyncio.QueueFull:
            logger.warning("[EVENT BUS] Queue is full! Dropping click event to protect server memory.")
            return False

    async def get_batch(
        self,
        max_batch_size: int = 50,
        timeout_seconds: float = 2.0,
    ) -> List[ClickEvent]:
        """
        Fetch a batch of events from the queue.
        Waits up to `timeout_seconds` or until `max_batch_size` is reached.
        """
        batch: List[ClickEvent] = []

        try:
            # Wait for at least the first event
            first_event = await asyncio.wait_for(
                self._queue.get(),
                timeout=timeout_seconds,
            )
            batch.append(first_event)
            self._queue.task_done()

            # Drain any additional pending events up to max_batch_size
            while len(batch) < max_batch_size and not self._queue.empty():
                event = self._queue.get_nowait()
                batch.append(event)
                self._queue.task_done()

        except asyncio.TimeoutError:
            pass

        return batch

    def qsize(self) -> int:
        """Current number of queued events."""
        return self._queue.qsize()


# Singleton instance of EventBus
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or initialize the singleton EventBus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
