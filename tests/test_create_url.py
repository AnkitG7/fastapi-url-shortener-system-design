# ======================================================
# tests/test_create_url.py — Tests for URL Creation
# ======================================================
# SYSTEM DESIGN CONCEPT: Test Organization
# -------------------------------------------------
# Tests are organized by FEATURE/ENDPOINT, not by file.
# Each test file covers ONE logical area:
#
#   test_create_url.py   → POST /api/v1/shorten
#   test_read_url.py     → GET endpoints
#   test_delete_url.py   → DELETE endpoint
#   test_redirect.py     → GET /{short_code} redirect
#   test_validation.py   → Input validation edge cases
#
# WHY? Because when a test fails, you immediately know
# WHICH FEATURE is broken by looking at the filename.
#
# SYSTEM DESIGN CONCEPT: Test Naming Convention
# -------------------------------------------------
# test_<action>_<condition>_<expected_result>
# Example: test_create_url_with_valid_data_returns_201
#
# Good test names read like documentation:
# "When I create a URL with valid data, I expect 201"
# ======================================================

from fastapi import status


class TestCreateURL:
    """
    Tests for POST /api/v1/shorten

    SYSTEM DESIGN CONCEPT: Test Classes as Logical Groups
    ----------------------------------------------------
    Grouping related tests in a class makes it easy to:
    1. Run only URL creation tests: pytest -k TestCreateURL
    2. See all creation scenarios at a glance
    3. Share setup logic (though we use fixtures instead)
    """

    # --------------------------------------------------
    # HAPPY PATH TESTS
    # --------------------------------------------------
    # Always write happy path tests FIRST. These verify
    # the feature works when everything is correct.
    # --------------------------------------------------

    def test_create_url_with_valid_data_returns_201(self, client):
        """
        The most basic test — can we create a short URL?

        WHAT THIS TESTS:
        - HTTP POST with valid JSON body
        - Server returns 201 Created
        - Response contains all expected fields
        """
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "https://www.google.com"},
        )

        assert response.status_code == status.HTTP_201_CREATED

        data = response.json()
        assert "short_code" in data
        assert data["original_url"] == "https://www.google.com/"
        assert data["click_count"] == 0
        assert data["expires_at"] is None

    def test_create_url_returns_short_url_with_base(self, client):
        """Verify the short_url includes the configured base URL."""
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "https://www.example.com"},
        )

        data = response.json()
        assert data["short_url"].startswith("http://localhost:8000/")
        assert data["short_code"] in data["short_url"]

    def test_create_url_generates_short_code_of_correct_length(self, client):
        """
        Short codes should be exactly 7 characters (as configured).

        WHY 7? It gives us 62^7 = ~3.5 TRILLION possible codes.
        That's enough for most URL shorteners. bit.ly uses 7 chars too.
        """
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "https://www.example.com"},
        )

        data = response.json()
        assert len(data["short_code"]) == 7

    def test_create_url_with_custom_code(self, client):
        """Users can choose their own short code."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "custom_code": "my-link",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["short_code"] == "my-link"
        assert data["short_url"] == "http://localhost:8000/my-link"

    def test_create_url_with_expiration(self, client):
        """URLs can be set to expire after N hours."""
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "expires_in_hours": 48,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["expires_at"] is not None

    def test_create_url_without_expiration_has_null_expires(self, client):
        """URLs without expiration should have null expires_at."""
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "https://www.example.com"},
        )

        data = response.json()
        assert data["expires_at"] is None

    def test_create_url_has_created_at_timestamp(self, client):
        """Every URL should have a created_at timestamp."""
        response = client.post(
            "/api/v1/shorten",
            json={"original_url": "https://www.example.com"},
        )

        data = response.json()
        assert data["created_at"] is not None

    def test_create_multiple_urls_get_unique_codes(self, client):
        """
        Each URL gets a UNIQUE short code.

        SYSTEM DESIGN CONCEPT: Uniqueness Guarantees
        --------------------------------------------
        In a distributed system, ensuring uniqueness is HARD.
        For now with in-memory storage, we retry until unique.
        In Phase 2 with a database, we'll use UNIQUE constraints.
        """
        codes = set()
        for i in range(10):
            response = client.post(
                "/api/v1/shorten",
                json={"original_url": f"https://www.example.com/page{i}"},
            )
            codes.add(response.json()["short_code"])

        # All 10 codes should be different
        assert len(codes) == 10

    # --------------------------------------------------
    # CONFLICT TESTS (409)
    # --------------------------------------------------

    def test_create_url_with_duplicate_custom_code_returns_409(self, client):
        """
        Trying to use a custom code that already exists returns 409 Conflict.

        SYSTEM DESIGN CONCEPT: Idempotency & Conflict Detection
        -------------------------------------------------------
        409 Conflict tells the client "the resource you're trying
        to create conflicts with an existing one." The client can
        then choose a different code or update the existing one.

        This is better than silently overwriting (data loss) or
        returning 500 (unhelpful).
        """
        # First creation succeeds
        client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.example.com",
                "custom_code": "taken",
            },
        )

        # Second creation with same code fails
        response = client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://www.other.com",
                "custom_code": "taken",
            },
        )

        assert response.status_code == status.HTTP_409_CONFLICT
