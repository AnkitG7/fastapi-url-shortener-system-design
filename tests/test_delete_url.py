# ======================================================
# tests/test_delete_url.py — Tests for URL Deletion
# ======================================================

from fastapi import status


class TestDeleteURL:
    """Tests for DELETE /api/v1/urls/{short_code}"""

    def test_delete_existing_url_returns_200(self, client, sample_url):
        """Deleting an existing URL returns a success message."""
        code = sample_url["short_code"]
        response = client.delete(f"/api/v1/urls/{code}")

        assert response.status_code == status.HTTP_200_OK
        assert "deleted" in response.json()["message"].lower()

    def test_delete_nonexistent_url_returns_404(self, client):
        """Deleting a URL that doesn't exist returns 404."""
        response = client.delete("/api/v1/urls/nonexistent")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deleted_url_no_longer_accessible(self, client, sample_url):
        """
        After deletion, the URL should not be retrievable.

        SYSTEM DESIGN CONCEPT: State Consistency
        ----------------------------------------
        After DELETE, all related endpoints (GET details,
        GET redirect, GET list) should reflect the deletion.
        This is CONSISTENCY — the system agrees with itself.

        In Phase 2 with a real DB, this is easier because
        DELETE is atomic. With in-memory storage, we need
        to make sure we clean up everywhere.
        """
        code = sample_url["short_code"]

        # Delete it
        client.delete(f"/api/v1/urls/{code}")

        # Verify it's gone from details
        response = client.get(f"/api/v1/urls/{code}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_deleted_url_removed_from_list(self, client, sample_url):
        """Deleted URL should not appear in the list endpoint."""
        code = sample_url["short_code"]

        # Delete it
        client.delete(f"/api/v1/urls/{code}")

        # Verify it's gone from the list
        response = client.get("/api/v1/urls")
        codes = [url["short_code"] for url in response.json()]
        assert code not in codes

    def test_deleted_url_redirect_returns_404(self, client, sample_url):
        """
        Deleted URL should not redirect — returns 404.

        This verifies that the redirect endpoint also
        respects the deletion (state consistency).
        """
        code = sample_url["short_code"]

        # Delete it
        client.delete(f"/api/v1/urls/{code}")

        # Verify redirect no longer works
        response = client.get(f"/{code}", follow_redirects=False)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_url_twice_second_returns_404(self, client, sample_url):
        """
        Deleting the same URL twice — second attempt returns 404.

        SYSTEM DESIGN CONCEPT: Idempotency of DELETE
        --------------------------------------------
        In strict REST, DELETE should be idempotent — calling
        it twice should have the same effect as calling once.
        However, most APIs return 404 on the second call to
        signal "it's already gone." Both approaches are valid.
        """
        code = sample_url["short_code"]

        # First delete
        response1 = client.delete(f"/api/v1/urls/{code}")
        assert response1.status_code == status.HTTP_200_OK

        # Second delete
        response2 = client.delete(f"/api/v1/urls/{code}")
        assert response2.status_code == status.HTTP_404_NOT_FOUND
