# ======================================================
# conftest.py — Shared Test Fixtures
# ======================================================
# SYSTEM DESIGN CONCEPT: Test Infrastructure
# -------------------------------------------------
# conftest.py is pytest's way of sharing setup/teardown
# logic across ALL test files. Think of it as the
# "test environment factory."
#
# KEY IDEAS:
# 1. FIXTURES — Reusable setup (like a test database, a
#    client, a logged-in user). Defined once, used everywhere.
# 2. ISOLATION — Each test gets a FRESH state so tests
#    don't interfere with each other. This is critical
#    because flaky tests destroy developer trust.
# 3. SCOPE — Fixtures can be per-test, per-module, or
#    per-session depending on how expensive they are.
#
# WHY IS TEST INFRASTRUCTURE IMPORTANT IN SYSTEM DESIGN?
# In production systems, automated tests are your SAFETY
# NET. Without them, every deploy is a gamble. Companies
# like Google run MILLIONS of tests before every release.
# ======================================================

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes.url import url_store


@pytest.fixture()
def client():
    """
    Create a fresh test client for each test.

    SYSTEM DESIGN CONCEPT: Test Client
    -----------------------------------
    FastAPI's TestClient lets you send HTTP requests to
    your app WITHOUT starting a real server. This means:

    1. Tests run in MILLISECONDS (no network overhead)
    2. Tests are DETERMINISTIC (no port conflicts)
    3. Tests are ISOLATED (no shared server state)

    Under the hood, it uses Starlette's TestClient which
    uses `httpx` — the same HTTP library used in production.
    So you're testing the REAL request/response pipeline.
    """
    # Clear the in-memory store before each test
    # This ensures TEST ISOLATION — each test starts clean
    url_store.clear()

    with TestClient(app) as c:
        yield c

    # Cleanup after each test
    url_store.clear()


@pytest.fixture()
def sample_url(client):
    """
    Fixture that creates a sample short URL and returns
    the response data.

    DESIGN PATTERN: Test Fixture / Test Data Factory
    ------------------------------------------------
    Many tests need a URL to already exist (for GET,
    DELETE, redirect, etc.). Instead of repeating the
    creation code in every test, we create it ONCE here.

    This is the DRY principle applied to tests.
    """
    response = client.post(
        "/api/v1/shorten",
        json={"original_url": "https://www.example.com/long/path"},
    )
    return response.json()


@pytest.fixture()
def sample_url_with_expiry(client):
    """Fixture that creates a URL with a 24-hour expiration."""
    response = client.post(
        "/api/v1/shorten",
        json={
            "original_url": "https://www.example.com/expiring",
            "expires_in_hours": 24,
        },
    )
    return response.json()


@pytest.fixture()
def sample_custom_url(client):
    """Fixture that creates a URL with a custom short code."""
    response = client.post(
        "/api/v1/shorten",
        json={
            "original_url": "https://www.example.com/custom",
            "custom_code": "my-link",
        },
    )
    return response.json()
