import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Video(Base):
    __tablename__ = "videos"

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "platform_video_id",
            name="uq_videos_platform_video_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    platform: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    platform_video_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    video_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    transcript: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    transcript_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    file_size_mb: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    thumbnail_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    author_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    view_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    like_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    comment_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
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

    @property
    def source_url(self) -> str:
        return self.video_url

    @source_url.setter
    def source_url(self, value: str) -> None:
        self.video_url = value
