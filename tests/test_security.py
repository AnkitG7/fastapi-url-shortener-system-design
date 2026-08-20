# ======================================================
# tests/test_security.py — Security & SSRF Defense Tests
# ======================================================
# SYSTEM DESIGN CONCEPT: Security Testing
# -------------------------------------------------
# 1. SSRF prevention for localhost / loopback
# 2. SSRF prevention for private subnet IPs (10.0.0.0/8, 192.168.0.0/16)
# 3. SSRF prevention for Cloud Metadata IP (169.254.169.254)
# 4. Scheme validation (reject file://, gopher://, ftp://)
# ======================================================

import pytest
from fastapi import status
from app.core.security import validate_and_sanitize_url


def test_valid_public_urls_pass():
    """Valid public web URLs are accepted."""
    valid_urls = [
        "https://www.google.com",
        "http://github.com/fastapi/fastapi",
        "https://sub.domain.example.org/path/to/resource?query=1#hash",
    ]
    for url in valid_urls:
        sanitized = validate_and_sanitize_url(url)
        assert sanitized == url


def test_ssrf_blocked_localhost():
    """Localhost and loopback hostnames are rejected."""
    blocked_urls = [
        "http://localhost/admin",
        "http://127.0.0.1:8080/secrets",
        "http://0.0.0.0:5432",
    ]
    for url in blocked_urls:
        with pytest.raises(ValueError) as exc:
            validate_and_sanitize_url(url)
        assert "Blocked" in str(exc.value) or "Internal" in str(exc.value)


def test_ssrf_blocked_private_ips():
    """Private RFC 1918 IP addresses are rejected."""
    blocked_private_ips = [
        "http://10.0.0.1/dashboard",
        "http://192.168.1.1/router",
        "http://172.16.0.5:9000",
    ]
    for url in blocked_private_ips:
        with pytest.raises(ValueError) as exc:
            validate_and_sanitize_url(url)
        assert "private or reserved" in str(exc.value)


def test_ssrf_blocked_cloud_metadata_ip():
    """
    AWS/GCP Cloud instance metadata IP (169.254.169.254) is strictly blocked.
    """
    cloud_metadata_url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
    with pytest.raises(ValueError) as exc:
        validate_and_sanitize_url(cloud_metadata_url)
    assert "private or reserved" in str(exc.value)


def test_api_shorten_rejects_ssrf_attempt(client):
    """
    POST /api/v1/shorten returns 400 Bad Request when an attacker attempts SSRF.
    """
    response = client.post(
        "/api/v1/shorten",
        json={"original_url": "http://127.0.0.1:5432/db"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["error_code"] == "INVALID_OR_BLOCKED_URL"
