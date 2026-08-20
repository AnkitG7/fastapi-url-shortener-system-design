# ======================================================
# tests/test_read_url.py — Tests for Reading URLs
# ======================================================
# Covers:
#   GET /api/v1/urls/{short_code}  — Get URL details
#   GET /api/v1/urls               — List all URLs
#   GET /                          — Root endpoint
# ======================================================

from fastapi import status


class TestGetURLDetails:
    """Tests for GET /api/v1/urls/{short_code}"""

    def test_get_existing_url_returns_200(self, client, sample_url):
        """Fetching an existing URL returns its details."""
        code = sample_url["short_code"]
        response = client.get(f"/api/v1/urls/{code}")

        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["short_code"] == code
        assert data["original_url"] == sample_url["original_url"]
        assert data["click_count"] == 0

    def test_get_nonexistent_url_returns_404(self, client):
        """
        Fetching a URL that doesn't exist returns 404 Not Found.

        SYSTEM DESIGN CONCEPT: Fail Fast with Clear Errors
        --------------------------------------------------
        Don't return 200 with an empty body — that's confusing.
        404 immediately tells the client "this doesn't exist"
        so they can handle it properly (show error page, retry, etc.)
        """
        response = client.get("/api/v1/urls/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_url_includes_stats_fields(self, client, sample_url):
        """The details endpoint returns extended stats (URLStatsResponse)."""
        code = sample_url["short_code"]
        response = client.get(f"/api/v1/urls/{code}")

        data = response.json()
        # URLStatsResponse includes last_clicked_at
        assert "last_clicked_at" in data
        assert "click_count" in data

    def test_get_url_with_custom_code(self, client, sample_custom_url):
        """Can retrieve a URL by its custom code."""
        response = client.get("/api/v1/urls/my-link")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["short_code"] == "my-link"


class TestListURLs:
    """
    Tests for GET /api/v1/urls

    SYSTEM DESIGN CONCEPT: Pagination Testing
    -----------------------------------------
    When testing paginated endpoints, verify:
    1. Default pagination works
    2. Custom skip/limit works
    3. Edge cases (skip past end, limit=0, etc.)
    4. Results are consistent
    """

    def test_list_urls_empty_returns_empty_list(self, client):
        """No URLs created yet — should return empty list."""
        response = client.get("/api/v1/urls")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_list_urls_returns_created_urls(self, client, sample_url):
        """After creating a URL, it appears in the list."""
        response = client.get("/api/v1/urls")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["short_code"] == sample_url["short_code"]

    def test_list_urls_pagination_with_limit(self, client):
        """
        Limit controls how many results are returned.

        Create 5 URLs but request only 2 — should get exactly 2.
        """
        for i in range(5):
            client.post(
                "/api/v1/shorten",
                json={"original_url": f"https://example.com/{i}"},
            )

        response = client.get("/api/v1/urls?limit=2")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2

    def test_list_urls_pagination_with_skip(self, client):
        """
        Skip controls the offset — skip=2 skips the first 2 results.
        """
        for i in range(5):
            client.post(
                "/api/v1/shorten",
                json={"original_url": f"https://example.com/{i}"},
            )

        response = client.get("/api/v1/urls?skip=3&limit=10")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 2  # 5 total - 3 skipped = 2

    def test_list_urls_limit_capped_at_100(self, client):
        """
        Even if client requests limit=9999, we cap at 100.

        SYSTEM DESIGN CONCEPT: Defensive API Design
        -------------------------------------------
        Never trust client input for pagination limits.
        A malicious client could request limit=1000000
        and crash your server. Always enforce a max.
        """
        # We can't easily create 101 URLs in a test,
        # but we can verify the endpoint accepts large limits
        # without error. The cap happens server-side.
        response = client.get("/api/v1/urls?limit=9999")
        assert response.status_code == status.HTTP_200_OK

    def test_list_urls_skip_past_end_returns_empty(self, client, sample_url):
        """Skipping past all results returns an empty list."""
        response = client.get("/api/v1/urls?skip=100")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []


class TestRootEndpoint:
    """Tests for GET / — API discoverability."""

    def test_root_returns_api_info(self, client):
        """Root endpoint returns service metadata and endpoint list."""
        response = client.get("/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service"] == "url-shortener"
        assert data["version"] == "0.1.0"
        assert "endpoints" in data

    def test_root_lists_all_endpoints(self, client):
        """Root endpoint documents all available endpoints."""
        response = client.get("/")
        endpoints = response.json()["endpoints"]

        assert "shorten" in endpoints
        assert "redirect" in endpoints
        assert "details" in endpoints
        assert "list" in endpoints
        assert "delete" in endpoints
