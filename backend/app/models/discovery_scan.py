import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DiscoveryScan(Base):
    __tablename__ = "discovery_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    center_location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    radius_m: Mapped[float] = mapped_column(
        Float,
        default=2000.0,
        nullable=False,
    )
    keywords_generated: Mapped[list | dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    videos_found_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
