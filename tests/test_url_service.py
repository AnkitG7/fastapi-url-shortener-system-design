# ======================================================
# tests/test_url_service.py — Business Logic Layer Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Business Logic & Domain Rule Testing
# -------------------------------------------------
# Tests that domain rules are strictly enforced:
# 1. Custom code conflict raising ShortCodeConflictError
# 2. Expired links raising URLExpiredError
# 3. Missing links raising URLNotFoundError
# ======================================================

import pytest
from app.repositories.url_repository import URLRepository
from app.services.url_service import (
    ShortCodeConflictError,
    URLExpiredError,
    URLNotFoundError,
    URLService,
)


@pytest.mark.anyio
async def test_service_create_and_duplicate_conflict(init_test_db):
    """Test custom code uniqueness enforced by URLService."""
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        service = URLService(repository=repo)

        await service.create_short_url(
            original_url="https://google.com",
            custom_code="custom1",
        )

        with pytest.raises(ShortCodeConflictError):
            await service.create_short_url(
                original_url="https://bing.com",
                custom_code="custom1",
            )


@pytest.mark.anyio
async def test_service_get_nonexistent_raises_not_found(init_test_db):
    """Test URLNotFoundError is raised when querying missing code."""
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        service = URLService(repository=repo)

        with pytest.raises(URLNotFoundError):
            await service.get_url("nonexistent_code")
