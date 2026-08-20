# ======================================================
# db/models.py — SQLAlchemy ORM Models (URL & Click Analytics)
# ======================================================
# SYSTEM DESIGN CONCEPT: Data Modeling for Analytics & High Throughput
# -------------------------------------------------
# 1. urls Table (Hot OLTP):
#    - Stores short code metadata and denormalized `click_count`.
#
# 2. clicks Table (Time-Series / Append-Only Event Log):
#    - Detailed click telemetry: timestamp, IP, user-agent, referrer.
#    - APPEND-ONLY: Writes are always INSERT (never UPDATE), which
#      is the fastest operation for relational databases.
#    - INDEXING: Composite index on `(url_id, timestamp)` for fast
#      time-range analytics queries (e.g., "clicks in the last 7 days").
# ======================================================

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class URL(Base):
    """
    Core table storing shortened URLs.
    """
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Internal ID",
    )

    short_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
        comment="Public short code",
    )

    original_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The original long URL",
    )

    click_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="Denormalized click counter for fast reads",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Creation timestamp",
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Expiration timestamp (NULL = never)",
    )

    last_clicked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="Last click timestamp",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="Last update timestamp",
    )

    # 1-to-many relationship with click events
    clicks: Mapped[List["Click"]] = relationship(
        "Click",
        back_populates="url",
        cascade="all, delete-orphan",  # Deleting a URL deletes all its click events
    )

    __table_args__ = (
        Index("ix_urls_created_at", "created_at"),
    )

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.now(timezone.utc)


class Click(Base):
    """
    SYSTEM DESIGN CONCEPT: Append-Only Event Log
    ---------------------------------------------
    Stores immutable telemetry for every click event.

    Why a separate table?
    - High-write volume doesn't lock the `urls` table.
    - Allows rich analytics (geographic, device breakdown, referrers).
    """
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    url_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # Supports IPv4 (15 chars) and IPv6 (45 chars)
        nullable=True,
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    referrer: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationship back to URL
    url: Mapped["URL"] = relationship("URL", back_populates="clicks")

    __table_args__ = (
        # Composite index for filtering clicks for a URL within a time window
        Index("ix_clicks_url_id_timestamp", "url_id", "timestamp"),
    )
