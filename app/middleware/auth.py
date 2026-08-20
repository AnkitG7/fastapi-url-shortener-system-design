# ======================================================
# middleware/auth.py — API Key Authentication & User Tiers
# ======================================================
# SYSTEM DESIGN CONCEPT: API Key Authentication & Tenancy
# -------------------------------------------------
# API Key auth provides:
# 1. IDENTIFICATION: Knowing WHO is making the request
# 2. AUTHORIZATION: Assigning permissions and tier limits
# 3. METRICS / BILLING: Tracking usage per tenant
# ======================================================

from typing import Optional
from dataclasses import dataclass
from app.core.security import UserTier


@dataclass
class AuthenticatedUser:
    """Represents the calling client context."""
    identifier: str
    tier: UserTier
    is_authenticated: bool


# Sample API keys for development / tiered testing
# In a full enterprise system, these are stored hashed in PostgreSQL
API_KEY_REGISTRY: dict[str, UserTier] = {
    "free-key-123": UserTier.FREE,
    "demo-free-key": UserTier.FREE,
    "premium-key-xyz": UserTier.PREMIUM,
    "demo-premium-key": UserTier.PREMIUM,
}


def authenticate_api_key(
    api_key: Optional[str],
    client_ip: str = "127.0.0.1",
) -> AuthenticatedUser:
    """
    Authenticate an incoming request based on X-API-Key header.

    If no API key is provided, falls back to ANONYMOUS tier keyed by Client IP.
    """
    if not api_key:
        return AuthenticatedUser(
            identifier=f"ip:{client_ip}",
            tier=UserTier.ANONYMOUS,
            is_authenticated=False,
        )

    api_key_clean = api_key.strip()
    if api_key_clean in API_KEY_REGISTRY:
        tier = API_KEY_REGISTRY[api_key_clean]
        return AuthenticatedUser(
            identifier=f"key:{api_key_clean}",
            tier=tier,
            is_authenticated=True,
        )

    # Unknown API key -> Treat as anonymous with specific key identifier
    return AuthenticatedUser(
        identifier=f"invalid_key:{api_key_clean}",
        tier=UserTier.ANONYMOUS,
        is_authenticated=False,
    )
