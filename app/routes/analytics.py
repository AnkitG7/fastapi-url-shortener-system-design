# ======================================================
# routes/analytics.py — Analytics API Endpoints
# ======================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.dependencies import enforce_rate_limit
from app.middleware.auth import AuthenticatedUser
from app.schemas.analytics import AnalyticsSummaryResponse
from app.schemas.url import ErrorResponse
from app.services.analytics_service import AnalyticsService
from app.services.url_service import URLNotFoundError

router = APIRouter(
    prefix="/api/v1/urls",
    tags=["Analytics"],
)


def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(session=db)


@router.get(
    "/{short_code}/analytics",
    response_model=AnalyticsSummaryResponse,
    summary="Get detailed click analytics",
    description="Retrieve aggregated telemetry: total clicks, 24h volume, top referrers, and user agents.",
    responses={
        404: {"model": ErrorResponse, "description": "URL not found"},
    },
)
async def get_analytics(
    short_code: str,
    user: AuthenticatedUser = Depends(enforce_rate_limit),
    service: AnalyticsService = Depends(get_analytics_service),
):
    """Fetch aggregated click analytics for a specific short code."""
    try:
        return await service.get_url_analytics(short_code)
    except URLNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "detail": str(e),
                "error_code": "URL_NOT_FOUND",
            },
        )
