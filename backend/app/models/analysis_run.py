import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    __table_args__ = (
        Index(
            "ix_analysis_runs_status_priority_created",
            "status",
            "priority",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    video_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("videos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submitted_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
        index=True,
    )
    trigger_source: Mapped[str] = mapped_column(
        String(50),
        default="USER_SUBMIT",
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    keyframes_data: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    ocr_data: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
    )
    execution_metrics: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    result_place_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("places.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
