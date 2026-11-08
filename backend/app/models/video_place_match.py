import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VideoPlaceMatch(Base):
    __tablename__ = "video_place_matches"

    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "place_id",
            name="uq_video_place_matches_video_place",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    place_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("places.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    confidence_status: Mapped[str] = mapped_column(
        String(20),
        default="MEDIUM",
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    match_method: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    evidence_sources: Mapped[list | dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    evidence: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    matched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
