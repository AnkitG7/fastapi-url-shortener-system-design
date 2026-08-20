# ======================================================
# tests/test_redirect.py — Tests for URL Redirection
# ======================================================
# The redirect is the CORE feature of a URL shortener.
# When someone visits http://localhost:8000/abc1234,
# they should be redirected to the original URL.
#
# SYSTEM DESIGN CONCEPT: Testing Behavior, Not Implementation
# -----------------------------------------------------------
# Notice we test WHAT the endpoint does (redirects, tracks clicks)
# not HOW it does it (incrementing a counter in a dict).
# This means when we swap to a database in Phase 2,
# these tests should STILL PASS without changes.
# ======================================================

from fastapi import status


class TestRedirect:
    """Tests for GET /{short_code} — the redirect endpoint."""

    def test_redirect_returns_307(self, client, sample_url):
        """
        Visiting a short URL returns 307 Temporary Redirect.

        NOTE: follow_redirects=False is critical here!
        Without it, the test client follows the redirect and
        we'd get the response from the DESTINATION, not our API.
        """
        code = sample_url["short_code"]
        response = client.get(f"/{code}", follow_redirects=False)

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT

    def test_redirect_location_header_points_to_original(self, client, sample_url):
        """
        The Location header contains the original URL.

        SYSTEM DESIGN CONCEPT: HTTP Headers
        -----------------------------------
        The Location header tells the browser WHERE to go.
        This is part of the HTTP spec (RFC 7231) — the browser
        reads this header and navigates there automatically.
        """
        code = sample_url["short_code"]
        response = client.get(f"/{code}", follow_redirects=False)

        assert response.headers["location"] == sample_url["original_url"]

    def test_redirect_increments_click_count(self, client, sample_url):
        """
        Each redirect increments the click counter.

        SYSTEM DESIGN CONCEPT: Side Effects in GET Requests
        --------------------------------------------------
        Strictly speaking, GET should be SAFE (no side effects).
        But click tracking is an accepted exception because:
        1. It doesn't change the RESOURCE (the URL)
        2. The client doesn't need to know about it
        3. The response is the same regardless

        In Phase 5, we'll make this truly non-blocking
        by processing clicks asynchronously.
        """
        code = sample_url["short_code"]

        # Click 3 times
        for _ in range(3):
            client.get(f"/{code}", follow_redirects=False)

        # Verify count
        response = client.get(f"/api/v1/urls/{code}")
        assert response.json()["click_count"] == 3

    def test_redirect_updates_last_clicked_at(self, client, sample_url):
        """After clicking, last_clicked_at should be set."""
        code = sample_url["short_code"]

        # Verify initially null
        response = client.get(f"/api/v1/urls/{code}")
        assert response.json()["last_clicked_at"] is None

        # Click once
        client.get(f"/{code}", follow_redirects=False)

        # Verify updated
        response = client.get(f"/api/v1/urls/{code}")
        assert response.json()["last_clicked_at"] is not None

    def test_redirect_nonexistent_code_returns_404(self, client):
        """Visiting a non-existent short code returns 404."""
        response = client.get("/nonexistent", follow_redirects=False)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_redirect_custom_code_works(self, client, sample_custom_url):
        """Custom codes redirect just like auto-generated ones."""
        response = client.get("/my-link", follow_redirects=False)

        assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert response.headers["location"] == sample_custom_url["original_url"]
