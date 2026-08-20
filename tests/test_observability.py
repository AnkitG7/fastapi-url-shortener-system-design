# ======================================================
# tests/test_observability.py — Observability & Tracing Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Observability & Probe Verification
# -------------------------------------------------
# 1. Automatic Correlation ID generation and reflection
# 2. Custom correlation ID propagation
# 3. Liveness probe (/health/live)
# 4. Readiness probe (/health/ready)
# ======================================================

from fastapi import status


def test_correlation_id_generated_and_returned(client):
    """
    Test that every request automatically receives a unique X-Correlation-ID header.
    """
    response = client.get("/api/v1/urls")
    assert response.status_code == status.HTTP_200_OK
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0


def test_custom_correlation_id_propagated(client):
    """
    Test that a client-provided X-Correlation-ID is preserved and echoed back.
    """
    custom_id = "trace-custom-uuid-12345"
    response = client.get("/api/v1/urls", headers={"X-Correlation-ID": custom_id})

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["X-Correlation-ID"] == custom_id


def test_liveness_probe_returns_200(client):
    """
    Test /health/live returns 200 OK with alive status.
    """
    response = client.get("/health/live")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "alive"}


def test_readiness_probe_returns_components(client):
    """
    Test /health/ready returns status for backing services.
    """
    response = client.get("/health/ready")
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE)
    data = response.json()
    assert "components" in data
    assert "postgres" in data["components"]
    assert "redis" in data["components"]
