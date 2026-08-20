# ======================================================
# config.py — Application Configuration
# ======================================================
# SYSTEM DESIGN CONCEPT: Configuration Management
# -------------------------------------------------
# In any real system, you need a SINGLE SOURCE OF TRUTH
# for configuration. Pydantic Settings gives us:
#
# 1. TYPE SAFETY — "5432" becomes int 5432 automatically
# 2. VALIDATION — App fails FAST at startup if config is wrong
# 3. DEFAULTS — Sensible defaults that can be overridden
# 4. DOCUMENTATION — The class itself documents all config options
#
# WHY IS THIS IMPORTANT?
# In production, misconfiguration is one of the TOP causes
# of outages. By validating config at startup, you catch
# errors BEFORE they cause problems at 3 AM.
# ======================================================

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    LOADING PRIORITY (highest to lowest):
    1. Environment variables (set in OS or Docker)
    2. .env file (for local development)
    3. Default values (defined here)

    This means in production, you set real env vars which
    override everything — no code changes needed.
    """

    # --- Application ---
    app_name: str = "url-shortener"
    app_version: str = "0.1.0"
    debug: bool = True
    base_url: str = "http://localhost:8000"

    # --- Database (Phase 2) ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/url_shortener"

    # --- Redis (Phase 3) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Rate Limiting (Phase 4) ---
    rate_limit_anonymous: int = 10
    rate_limit_free: int = 100
    rate_limit_premium: int = 1000

    # --- Short URL Config ---
    short_code_length: int = 7  # Length of generated short codes

    model_config = {
        "env_file": ".env",       # Load from .env file
        "env_file_encoding": "utf-8",
        "case_sensitive": False,   # APP_NAME and app_name both work
    }


@lru_cache()
def get_settings() -> Settings:
    """
    SYSTEM DESIGN CONCEPT: Singleton Pattern via Caching
    ---------------------------------------------------
    lru_cache ensures we create Settings ONLY ONCE.

    WHY? Because:
    1. Reading .env file on every request = wasteful I/O
    2. Settings don't change at runtime
    3. Every part of the app gets the SAME config object

    This is a lightweight version of the Singleton pattern.
    In larger systems, you'd use a dedicated config service
    (like Consul or AWS Parameter Store).
    """
    return Settings()
