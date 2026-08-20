# ======================================================
# tests/test_url_repository.py — Repository Layer Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Data Access Testing
# -------------------------------------------------
# Testing the repository directly ensures:
# 1. SQL queries are syntactically and semantically correct
# 2. Indexes and uniqueness constraints function as expected
# 3. Atomic operations (like increment_click) work without race conditions
# ======================================================

import pytest
from app.db.models import URL
from app.repositories.url_repository import URLRepository


@pytest.mark.anyio
async def test_repository_create_and_get(init_test_db):
    """Test creating and retrieving a URL record via repository."""
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        url = URL(
            short_code="test1234",
            original_url="https://www.example.com",
        )
        created = await repo.create(url)
        assert created.id is not None
        assert created.short_code == "test1234"

        fetched = await repo.get_by_short_code("test1234")
        assert fetched is not None
        assert fetched.original_url == "https://www.example.com"
        assert fetched.click_count == 0


@pytest.mark.anyio
async def test_repository_atomic_increment_click(init_test_db):
    """Test atomic click incrementing at the DB level."""
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        url = URL(
            short_code="click123",
            original_url="https://www.example.com/click",
        )
        await repo.create(url)

        # Increment twice
        updated1 = await repo.increment_click("click123")
        assert updated1.click_count == 1
        assert updated1.last_clicked_at is not None

        updated2 = await repo.increment_click("click123")
        assert updated2.click_count == 2


@pytest.mark.anyio
async def test_repository_delete(init_test_db):
    """Test deleting a URL from repository."""
    from tests.conftest import TestingSessionLocal

    async with TestingSessionLocal() as session:
        repo = URLRepository(session=session)
        url = URL(
            short_code="del123",
            original_url="https://www.example.com/delete",
        )
        await repo.create(url)

        deleted = await repo.delete_by_short_code("del123")
        assert deleted is True

        fetched = await repo.get_by_short_code("del123")
        assert fetched is None
