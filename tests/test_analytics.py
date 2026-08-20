# ======================================================
# tests/test_analytics.py — Analytics & Background Worker Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Analytics Telemetry & Worker Verification
# -------------------------------------------------
# 1. Batch worker bulk insert execution
# 2. Aggregation queries (24h counts, top referrers, top user agents)
# 3. Analytics API endpoint verification
# ======================================================

import asyncio
from datetime import datetime, timezone
import pytest
from fastapi import status
from sqlalchemy import select

from app.db.models import Click, URL
from app.events.event_bus import ClickEvent, EventBus
from app.services.analytics_service import AnalyticsService
from app.workers.analytics_worker import AnalyticsWorker


@pytest.mark.anyio
async def test_analytics_worker_flushes_batch_to_db(init_test_db):
    """
    Test that AnalyticsWorker consumes queued ClickEvents and bulk inserts them into DB.
    """
    from tests.conftest import TestingSessionLocal

    bus = EventBus()
    worker = AnalyticsWorker(
        event_bus=bus,
        session_factory=TestingSessionLocal,
        batch_size=10,
        flush_interval_seconds=0.1,
    )

    # 1. Create a URL record first
    async with TestingSessionLocal() as session:
        url = URL(short_code="worker_test", original_url="https://example.com")
        session.add(url)
        await session.commit()
        await session.refresh(url)
        url_id = url.id

    # 2. Queue 3 click events
    for i in range(3):
        await bus.publish(
            ClickEvent(
                short_code="worker_test",
                url_id=url_id,
                ip_address=f"10.0.0.{i}",
                user_agent="Mozilla/5.0",
                referrer="https://twitter.com",
            )
        )

    # 3. Manually trigger worker batch flush
    batch = await bus.get_batch(max_batch_size=10, timeout_seconds=0.5)
    await worker._flush_batch(batch)

    # 4. Verify rows inserted in `clicks` table
    async with TestingSessionLocal() as session:
        stmt = select(Click).where(Click.url_id == url_id)
        res = await session.execute(stmt)
        clicks = res.scalars().all()
        assert len(clicks) == 3
        assert clicks[0].referrer == "https://twitter.com"

        # Verify denormalized click count updated on URL
        stmt_url = select(URL).where(URL.id == url_id)
        res_url = await session.execute(stmt_url)
        url_updated = res_url.scalar_one()
        assert url_updated.click_count == 3


@pytest.mark.anyio
async def test_analytics_service_aggregations(init_test_db):
    """
    Test AnalyticsService aggregates top referrers and user agents.
    """
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        # Create URL
        url = URL(short_code="stats_test", original_url="https://example.com", click_count=4)
        session.add(url)
        await session.commit()
        await session.refresh(url)

        # Insert click telemetry rows
        clicks = [
            Click(url_id=url.id, referrer="https://google.com", user_agent="Chrome"),
            Click(url_id=url.id, referrer="https://google.com", user_agent="Chrome"),
            Click(url_id=url.id, referrer="https://github.com", user_agent="Firefox"),
            Click(url_id=url.id, referrer=None, user_agent="Safari"),
        ]
        session.add_all(clicks)
        await session.commit()

        # Compute analytics
        service = AnalyticsService(session=session)
        analytics = await service.get_url_analytics("stats_test")

        assert analytics.short_code == "stats_test"
        assert analytics.total_clicks == 4
        assert analytics.clicks_last_24h == 4

        # Verify top referrers
        assert analytics.top_referrers[0].referrer == "https://google.com"
        assert analytics.top_referrers[0].count == 2

        # Verify top user agents
        assert analytics.top_user_agents[0].user_agent == "Chrome"
        assert analytics.top_user_agents[0].count == 2


def test_api_get_analytics_endpoint(client, sample_url):
    """
    Test GET /api/v1/urls/{short_code}/analytics returns summary metrics.
    """
    code = sample_url["short_code"]
    response = client.get(f"/api/v1/urls/{code}/analytics")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["short_code"] == code
    assert "total_clicks" in data
    assert "clicks_last_24h" in data
    assert "top_referrers" in data
    assert "top_user_agents" in data
