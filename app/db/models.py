# ======================================================
# db/models.py — SQLAlchemy ORM Models (Database Tables)
# ======================================================
# SYSTEM DESIGN CONCEPT: Database Schema Design
# -------------------------------------------------
# Your database schema is the FOUNDATION of your system.
# A bad schema leads to:
# 1. SLOW queries (missing indexes, poor normalization)
# 2. DATA inconsistencies (no constraints, no foreign keys)
# 3. PAINFUL migrations (hard to change later)
# 4. SCALABILITY issues (can't partition, can't shard)
#
# KEY PRINCIPLES we follow here:
#
# 1. NORMALIZATION — Each fact stored in ONE place
#    (url data in `urls` table, click data in `clicks` table)
#
# 2. INDEXING — Add indexes on columns you QUERY BY
#    (short_code, created_at) but NOT on every column
#    because indexes slow down WRITES.
#
# 3. CONSTRAINTS — Let the DATABASE enforce rules
#    (UNIQUE short_code, NOT NULL original_url).
#    Application bugs come and go, but DB constraints
#    are your last line of defense for data integrity.
#
# 4. TIMESTAMPS — Always track created_at / updated_at.
#    You'll thank yourself during debugging at 3 AM.
#
# SYSTEM DESIGN CONCEPT: ORM (Object-Relational Mapping)
# -------------------------------------------------
# An ORM maps Python classes to database tables:
#   Python class URL → SQL table "urls"
#   Python attribute url.short_code → SQL column "short_code"
#
# TRADEOFFS of using an ORM:
# + Easier to write (Python instead of raw SQL)
# + Database-agnostic (switch Postgres to MySQL easily)
# + Prevents SQL injection (parameterized queries)
# - Performance overhead (ORM generates SQL, not always optimal)
# - Complex queries are harder to express
# - "Leaky abstraction" — you still need to understand SQL
#
# Rule of thumb: Use ORM for 90% of queries, raw SQL for
# the remaining 10% that need optimization.
# ======================================================

from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Index,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    SYSTEM DESIGN CONCEPT: Inheritance in Schema Design
    ---------------------------------------------------
    All models inherit from this Base class. SQLAlchemy
    uses it to:
    1. Track all models (for migration generation)
    2. Share common behavior (like timestamp columns)
    3. Generate the metadata (table definitions)

    This is the TEMPLATE METHOD pattern — the base class
    defines the structure, subclasses fill in the details.
    """
    pass


class URL(Base):
    """
    Represents a shortened URL in the database.

    TABLE: urls
    -------------------------------------------------
    This is the CORE table of our system. Every short URL
    created by users lives here.

    SCHEMA DESIGN DECISIONS:

    1. `id` (Integer PK) — Internal identifier, NEVER exposed
       to clients. We use `short_code` as the public identifier.
       WHY? Sequential IDs are guessable. If someone knows
       ID 100 exists, they can try 101, 102, etc.

    2. `short_code` (String, UNIQUE, INDEXED) — The public
       identifier. UNIQUE constraint prevents duplicates at
       the DATABASE level (even if app logic fails).
       INDEXED because every redirect does a lookup by this.

    3. `original_url` (Text) — We use Text instead of String
       because URLs can be VERY long (up to 2083 chars in
       some browsers, theoretically unlimited in the spec).

    4. `click_count` (Integer, default=0) — Denormalized
       counter. In strict normalization, we'd COUNT from the
       clicks table. But that's a full table scan for a
       frequently-accessed number. This is an intentional
       DENORMALIZATION for read performance.
       TRADEOFF: Faster reads, slightly more complex writes.

    5. `created_at` / `updated_at` — Server-side timestamps.
       Using `server_default=func.now()` means the DATABASE
       generates the timestamp, not Python. This is important
       because in distributed systems, server clocks can drift.
    """

    __tablename__ = "urls"

    # --- Primary Key ---
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Internal ID — never exposed to API clients",
    )

    # --- Core Fields ---
    short_code: Mapped[str] = mapped_column(
        String(20),
        unique=True,       # DB-level uniqueness guarantee
        nullable=False,
        index=True,        # B-tree index for fast lookups
        comment="Public short code (e.g., 'abc1234')",
    )

    original_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The original long URL",
    )

    # --- Metadata ---
    click_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        comment="Denormalized click counter for fast reads",
    )

    # --- Timestamps ---
    # SYSTEM DESIGN CONCEPT: Server-Side vs Client-Side Timestamps
    # Using func.now() makes the DATABASE generate the timestamp.
    # This ensures consistency even if app servers have clock drift.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this URL was created",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,       # NULL = never expires
        default=None,
        comment="When this URL expires (NULL = never)",
    )

    last_clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        comment="When this URL was last clicked",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),  # Auto-update on any change
        nullable=False,
        comment="Last modification timestamp",
    )

    # --- Indexes ---
    # SYSTEM DESIGN CONCEPT: Composite & Conditional Indexes
    # -------------------------------------------------
    # Beyond the single-column index on short_code, we add:
    #
    # 1. Index on created_at — for pagination/sorting by date
    #    ("show me the newest URLs")
    #
    # Think of indexes like a book's index:
    # Without it, you scan EVERY page (full table scan).
    # With it, you jump directly to the right page.
    #
    # BUT indexes aren't free:
    # - Each index uses DISK SPACE
    # - Each INSERT/UPDATE must update ALL indexes
    # - Too many indexes slow down WRITES
    #
    # Rule: Index columns you FILTER or SORT by frequently.
    __table_args__ = (
        Index("ix_urls_created_at", "created_at"),
        {"comment": "Core table storing all shortened URLs"},
    )

    def __repr__(self) -> str:
        return f"<URL(short_code='{self.short_code}', clicks={self.click_count})>"

    def is_expired(self) -> bool:
        """Check if this URL has expired."""
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.now(timezone.utc)
