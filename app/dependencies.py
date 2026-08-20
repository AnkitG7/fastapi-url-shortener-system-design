# ======================================================
# dependencies.py — Dependency Injection Providers
# ======================================================
# SYSTEM DESIGN CONCEPT: Dependency Injection (DI)
# -------------------------------------------------
# Dependency Injection is a design pattern where an object
# receives other objects that it depends on, rather than
# creating them internally.
#
# BENEFITS:
# 1. DECOUPLING: Route handlers don't need to know how to
#    construct Database Sessions, Repositories, or Services.
# 2. TESTABILITY: Easily swap real services/repositories with
#    mocks or in-memory equivalents during testing.
# 3. LIFECYCLE MANAGEMENT: FastAPI automatically handles
#    opening and closing resources per request.
# ======================================================

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repositories.url_repository import URLRepository
from app.services.url_service import URLService


async def get_url_repository(
    db: AsyncSession = Depends(get_db),
) -> URLRepository:
    """Provide a URLRepository instance bound to the request's DB session."""
    return URLRepository(session=db)


async def get_url_service(
    repository: URLRepository = Depends(get_url_repository),
) -> URLService:
    """Provide a URLService instance with injected repository."""
    return URLService(repository=repository)
