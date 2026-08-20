# ======================================================
# dependencies.py — Dependency Injection Providers
# ======================================================
# SYSTEM DESIGN CONCEPT: Dependency Injection (DI)
# -------------------------------------------------
# We provide URLCache alongside URLRepository to URLService.
# ======================================================

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.url_cache import URLCache
from app.db.database import get_db
from app.repositories.url_repository import URLRepository
from app.services.url_service import URLService


async def get_url_cache() -> URLCache:
    """Provide a URLCache instance."""
    return URLCache()


async def get_url_repository(
    db: AsyncSession = Depends(get_db),
) -> URLRepository:
    """Provide a URLRepository instance bound to the request's DB session."""
    return URLRepository(session=db)


async def get_url_service(
    repository: URLRepository = Depends(get_url_repository),
    cache: URLCache = Depends(get_url_cache),
) -> URLService:
    """Provide a URLService instance with injected repository and cache."""
    return URLService(repository=repository, cache=cache)
