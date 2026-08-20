# ======================================================
# schemas/url.py — Request & Response Data Contracts
# ======================================================
# SYSTEM DESIGN CONCEPT: API Contracts & Data Validation
# -------------------------------------------------
# In system design, the "contract" between client and
# server is CRITICAL. If the client sends garbage,
# your server shouldn't crash — it should reject it
# with a clear error message.
#
# Pydantic models serve as:
# 1. INPUT VALIDATION — Reject bad data before it hits your logic
# 2. OUTPUT SERIALIZATION — Ensure responses have a consistent shape
# 3. DOCUMENTATION — Auto-generates OpenAPI/Swagger docs
# 4. TYPE SAFETY — IDE autocomplete and error checking
#
# REAL-WORLD ANALOGY:
# Think of these schemas like a restaurant order form.
# The form has specific fields (appetizer, main, drink).
# If someone writes "car" in the appetizer field, the
# waiter rejects it BEFORE sending it to the kitchen.
# Same idea — validate at the BOUNDARY, not deep inside.
# ======================================================

from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Optional


# -------------------------------------------------------
# REQUEST SCHEMAS — What the client SENDS to us
# -------------------------------------------------------

class URLCreateRequest(BaseModel):
    """
    Schema for creating a new short URL.

    DESIGN DECISION: Why separate Request and Response models?
    ---------------------------------------------------------
    Because they serve different purposes:
    - Request: What the client is ALLOWED to send
    - Response: What the server CHOOSES to return

    The client should NOT be able to set the short_code,
    click_count, or created_at — those are server-controlled.
    This is the PRINCIPLE OF LEAST PRIVILEGE applied to APIs.
    """

    original_url: HttpUrl = Field(
        ...,  # ... means REQUIRED (no default value)
        description="The original URL to shorten",
        examples=["https://www.example.com/very/long/path/to/resource"]
    )

    custom_code: Optional[str] = Field(
        None,  # None means OPTIONAL
        min_length=3,
        max_length=20,
        pattern=r"^[a-zA-Z0-9_-]+$",  # Only alphanumeric, underscore, hyphen
        description="Optional custom short code (e.g., 'my-link')",
        examples=["my-cool-link"]
    )

    expires_in_hours: Optional[int] = Field(
        None,
        ge=1,       # Greater than or equal to 1
        le=8760,    # Max 1 year (365 * 24)
        description="Hours until the link expires (optional)",
        examples=[24, 168, 720]
    )


# -------------------------------------------------------
# RESPONSE SCHEMAS — What the server SENDS back
# -------------------------------------------------------

class URLResponse(BaseModel):
    """
    Schema for a URL response.

    DESIGN DECISION: Never expose internal IDs directly
    --------------------------------------------------
    Notice we return `short_code` as the identifier,
    not the database primary key. This is because:

    1. Internal IDs leak implementation details
    2. Sequential IDs let attackers enumerate all URLs
    3. Short codes are the "public API" of our service

    This is the concept of INFORMATION HIDING — a
    fundamental principle in system design.
    """

    short_code: str = Field(
        ...,
        description="The generated short code",
        examples=["abc1234"]
    )

    original_url: str = Field(
        ...,
        description="The original URL",
        examples=["https://www.example.com/very/long/path"]
    )

    short_url: str = Field(
        ...,
        description="The full shortened URL",
        examples=["http://localhost:8000/abc1234"]
    )

    created_at: datetime = Field(
        ...,
        description="When the URL was created"
    )

    expires_at: Optional[datetime] = Field(
        None,
        description="When the URL expires (null = never)"
    )

    click_count: int = Field(
        default=0,
        description="Number of times this URL has been clicked"
    )


class URLStatsResponse(URLResponse):
    """
    Extended response with analytics data.

    DESIGN DECISION: Schema Inheritance
    -----------------------------------
    This extends URLResponse — DRY (Don't Repeat Yourself).
    In system design, we avoid duplicating data structures
    because changes need to be made in only ONE place.
    """

    last_clicked_at: Optional[datetime] = Field(
        None,
        description="When the URL was last clicked"
    )


# -------------------------------------------------------
# ERROR SCHEMAS — Consistent error responses
# -------------------------------------------------------

class ErrorResponse(BaseModel):
    """
    Standard error response format.

    SYSTEM DESIGN CONCEPT: Consistent Error Contracts
    ------------------------------------------------
    Every API should return errors in a CONSISTENT format.
    This lets clients write ONE error handler instead of
    guessing what shape each error might be.

    Good APIs make errors as informative as successes.
    """

    detail: str = Field(
        ...,
        description="Human-readable error message",
        examples=["URL not found"]
    )

    error_code: str = Field(
        ...,
        description="Machine-readable error code for programmatic handling",
        examples=["URL_NOT_FOUND"]
    )


class MessageResponse(BaseModel):
    """Simple message response for operations like DELETE."""

    message: str = Field(
        ...,
        description="Success message",
        examples=["URL deleted successfully"]
    )
