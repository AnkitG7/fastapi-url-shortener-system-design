# ======================================================
# services/analytics_service.py — Analytics Aggregation Service
# ======================================================
# SYSTEM DESIGN CONCEPT: Read/Write Segregation (CQRS Light)
# -------------------------------------------------
# - Write Path: High-throughput async Event Bus + Batch Worker
# - Read Path: Grouped SQL aggregations with indexed timestamp ranges
# ======================================================

from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Click, URL
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    ReferrerCount,
    UserAgentCount,
)
from app.services.url_service import URLNotFoundError


class AnalyticsService:
    """Service for computing analytics aggregations on click event logs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_url_analytics(self, short_code: str) -> AnalyticsSummaryResponse:
        """
        Compute aggregate analytics for a given short code.
        """
        # 1. Fetch URL metadata
        stmt_url = select(URL).where(URL.short_code == short_code)
        res_url = await self.session.execute(stmt_url)
        url_obj = res_url.scalar_one_or_none()

        if url_obj is None:
            raise URLNotFoundError(short_code)

        # 2. Count clicks in last 24h
        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(hours=24)

        stmt_24h = (
            select(func.count(Click.id))
            .where(Click.url_id == url_obj.id, Click.timestamp >= one_day_ago)
        )
        res_24h = await self.session.execute(stmt_24h)
        clicks_24h = res_24h.scalar_one() or 0

        # 3. Top 5 Referrers
        stmt_ref = (
            select(
                func.coalesce(Click.referrer, "Direct").label("ref"),
                func.count(Click.id).label("count"),
            )
            .where(Click.url_id == url_obj.id)
            .group_by("ref")
            .order_by(desc("count"))
            .limit(5)
        )
        res_ref = await self.session.execute(stmt_ref)
        top_referrers = [
            ReferrerCount(referrer=row.ref, count=row.count)
            for row in res_ref.all()
        ]

        # 4. Top 5 User Agents
        stmt_ua = (
            select(
                func.coalesce(Click.user_agent, "Unknown").label("ua"),
                func.count(Click.id).label("count"),
            )
            .where(Click.url_id == url_obj.id)
            .group_by("ua")
            .order_by(desc("count"))
            .limit(5)
        )
        res_ua = await self.session.execute(stmt_ua)
        top_user_agents = [
            UserAgentCount(user_agent=row.ua, count=row.count)
            for row in res_ua.all()
        ]

        return AnalyticsSummaryResponse(
            short_code=url_obj.short_code,
            original_url=url_obj.original_url,
            total_clicks=url_obj.click_count,
            clicks_last_24h=clicks_24h,
            top_referrers=top_referrers,
            top_user_agents=top_user_agents,
        )
