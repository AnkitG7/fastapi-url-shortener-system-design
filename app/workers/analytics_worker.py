# ======================================================
# workers/analytics_worker.py — Background Batch Analytics Worker
# ======================================================
# SYSTEM DESIGN CONCEPT: Background Workers & Batch Writes
# -------------------------------------------------
# Supports dependency injection of session_factory for
# 100% test isolation.
# ======================================================

import asyncio
import logging
from typing import Callable, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.database import async_session_factory
from app.db.models import Click, URL
from app.events.event_bus import ClickEvent, EventBus, get_event_bus

logger = logging.getLogger(__name__)


class AnalyticsWorker:
    """
    Background worker that continuously consumes ClickEvents from the EventBus
    and writes them in efficient batches to PostgreSQL.
    """

    def __init__(
        self,
        event_bus: EventBus,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        batch_size: int = 50,
        flush_interval_seconds: float = 2.0,
    ):
        self.event_bus = event_bus
        self.session_factory = session_factory or async_session_factory
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start the background consumer loop."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop())
            logger.info("[ANALYTICS WORKER] Background consumer worker started.")

    async def stop(self) -> None:
        """Graceful drain and shutdown."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Final drain of any remaining events in queue
        remaining_events: List[ClickEvent] = []
        while self.event_bus.qsize() > 0:
            events = await self.event_bus.get_batch(max_batch_size=100, timeout_seconds=0.1)
            remaining_events.extend(events)

        if remaining_events:
            logger.info(f"[ANALYTICS WORKER] Flushing {len(remaining_events)} remaining events on shutdown...")
            await self._flush_batch(remaining_events)

        logger.info("[ANALYTICS WORKER] Background worker stopped cleanly.")

    async def _run_loop(self) -> None:
        """Main consumer loop."""
        while self._running:
            try:
                batch = await self.event_bus.get_batch(
                    max_batch_size=self.batch_size,
                    timeout_seconds=self.flush_interval,
                )

                if batch:
                    await self._flush_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[ANALYTICS WORKER] Error in consumer loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _flush_batch(self, events: List[ClickEvent]) -> None:
        """
        Execute bulk INSERT into the clicks table and increment URL click counts.
        """
        if not events:
            return

        async with self.session_factory() as session:
            try:
                # 1. Resolve URL IDs for short codes in batch
                short_codes = list({e.short_code for e in events})
                stmt = select(URL.id, URL.short_code).where(URL.short_code.in_(short_codes))
                result = await session.execute(stmt)
                code_to_id = {row.short_code: row.id for row in result.all()}

                # 2. Build Click ORM instances for bulk insert
                click_models: List[Click] = []
                code_counts: dict[str, int] = {}

                for e in events:
                    url_id = e.url_id or code_to_id.get(e.short_code)
                    if url_id:
                        click_models.append(
                            Click(
                                url_id=url_id,
                                timestamp=e.timestamp,
                                ip_address=e.ip_address,
                                user_agent=e.user_agent,
                                referrer=e.referrer,
                            )
                        )
                        code_counts[e.short_code] = code_counts.get(e.short_code, 0) + 1

                # 3. Bulk insert click records
                if click_models:
                    session.add_all(click_models)

                # 4. Bulk update click counts on URLs
                for short_code, count in code_counts.items():
                    update_stmt = (
                        update(URL)
                        .where(URL.short_code == short_code)
                        .values(click_count=URL.click_count + count)
                    )
                    await session.execute(update_stmt)

                await session.commit()
                logger.debug(f"[ANALYTICS WORKER] Flushed batch of {len(click_models)} click events to DB.")

            except Exception as e:
                await session.rollback()
                logger.error(f"[ANALYTICS WORKER] Failed to flush batch: {e}", exc_info=True)


# Singleton instance
_analytics_worker: AnalyticsWorker | None = None


def get_analytics_worker() -> AnalyticsWorker:
    global _analytics_worker
    if _analytics_worker is None:
        _analytics_worker = AnalyticsWorker(event_bus=get_event_bus())
    return _analytics_worker
