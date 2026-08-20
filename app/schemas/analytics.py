# ======================================================
# schemas/analytics.py — Analytics Data Contracts
# ======================================================
# SYSTEM DESIGN CONCEPT: CQRS Query Schemas
# -------------------------------------------------
# Rich aggregation models for telemetry & reporting.
# ======================================================

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ReferrerCount(BaseModel):
    referrer: str = Field(..., description="Referrer URL domain or direct")
    count: int = Field(..., description="Total clicks from this referrer")


class UserAgentCount(BaseModel):
    user_agent: str = Field(..., description="Browser or client device")
    count: int = Field(..., description="Total clicks from this device")


class AnalyticsSummaryResponse(BaseModel):
    """Aggregated analytics summary for a shortened URL."""
    short_code: str
    original_url: str
    total_clicks: int
    clicks_last_24h: int
    top_referrers: List[ReferrerCount] = []
    top_user_agents: List[UserAgentCount] = []
