"""User watchlists, custom asset tags, and research bookmarks."""

from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base
from src.utils.time import utc_now


class WatchlistItem(Base):
    """User-tracked asset bookmark with custom tags and notes."""

    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default="default_user", index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    tags: Mapped[str] = mapped_column(String(256), default="")  # e.g., "alpha,l1,accumulating"
    notes: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
