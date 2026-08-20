# ======================================================
# tests/test_validation.py — Input Validation Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Boundary Testing
# -------------------------------------------------
# Validation tests verify that your API REJECTS bad input.
# These are just as important as happy-path tests because:
#
# 1. SECURITY — Unvalidated input is the #1 attack vector
#    (SQL injection, XSS, SSRF all start with bad input)
# 2. DATA INTEGRITY — Garbage in = garbage out
# 3. USER EXPERIENCE — Clear error messages help clients
#
# The principle: "Be liberal in what you accept, be
# conservative in what you send" (Postel's Law) — but
# with security in mind, VALIDATE EVERYTHING.
# ======================================================

from fastapi import status


class TestURLValidation:
    """Tests that verify Pydantic validation rejects bad input."""

    def test_missing_url_returns_422(self, client):
        """
        Sending an empty body returns 422 Unprocessable Entity.

        SYSTEM DESIGN CONCEPT: 422 vs 400
        ---------------------------------
        - 400 Bad Request: Malformed request (bad JSON, wrong content-type)
        - 422 Unprocessable Entity: Valid JSON, but data fails validation

        FastAPI uses 422 for validation errors, which is more specific.
        This helps clients distinguish between "your JSON is broken"
        and "your data doesn't meet the requirements."
        """
        response = client.post("/api/v1/shorten", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_invalid_url_format_returns_422(self, client):
        """URLs must be valid HTTP/HTTPS URLs."""
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "not-a-valid-url"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_url_without_scheme_returns_422(self, client):
        """URLs must include http:// or https://."""
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "www.example.com"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_empty_string_url_returns_422(self, client):
        """Empty string is not a valid URL."""
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCustomCodeValidation:
    """Tests for custom_code field validation."""

    def test_custom_code_too_short_returns_422(self, client):
        """Custom codes must be at least 3 characters."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "custom_code": "ab",  # min_length=3
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_custom_code_too_long_returns_422(self, client):
        """Custom codes must be at most 20 characters."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "custom_code": "a" * 21,  # max_length=20
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_custom_code_with_special_chars_returns_422(self, client):
        """
        Custom codes only allow alphanumeric, underscore, hyphen.

        WHY? Because special characters in URLs cause encoding
        issues (spaces become %20, etc.) and make URLs ugly.
        """
        invalid_codes = ["has space", "has@symbol", "has/slash", "has.dot", "has?query"]

        for code in invalid_codes:
            response = client.post(
                "/api/v1/shorten",
                json={
                    "original_url": "https://www.example.com",
                    "custom_code": code,
                },
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, \
                f"Expected 422 for custom_code='{code}'"

    def test_custom_code_with_valid_special_chars(self, client):
        """Underscores and hyphens are allowed in custom codes."""
        valid_codes = ["my-link", "my_link", "abc-123_xyz"]

        for code in valid_codes:
            response = client.post(
                "/api/v1/shorten",
                json={
                    "original_url": "https://www.example.com",
                    "custom_code": code,
                },
            )
            assert response.status_code == status.HTTP_201_CREATED, \
                f"Expected 201 for custom_code='{code}'"


class TestExpirationValidation:
    """Tests for expires_in_hours field validation."""

    def test_expiration_zero_returns_422(self, client):
        """Expiration must be at least 1 hour."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "expires_in_hours": 0,  # ge=1
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_expiration_negative_returns_422(self, client):
        """Negative expiration makes no sense."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "expires_in_hours": -5,
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_expiration_over_one_year_returns_422(self, client):
        """Expiration can't exceed 8760 hours (1 year)."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "expires_in_hours": 8761,  # le=8760
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_expiration_at_max_is_valid(self, client):
        """Exactly 8760 hours (1 year) should be accepted."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "expires_in_hours": 8760,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_expiration_at_min_is_valid(self, client):
        """Exactly 1 hour should be accepted."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "expires_in_hours": 1,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
