from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str | None = None
    normalized_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    category: str | None = None
    source: str | None = None
    phone_number: str | None = None
    website_url: str | None = None
    created_at: datetime
    updated_at: datetime


class PlaceMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    is_saved: bool = False


class VideoMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | UUID
    platform: str
    platform_video_id: str
    video_url: str
    title: str | None = None
    caption: str | None = None
    duration_seconds: float | None = None
    thumbnail_url: str | None = None
    author_name: str | None = None
    created_at: datetime
    is_saved: bool = False


class MatchInfo(BaseModel):
    confidence_status: str
    evidence_sources: list | dict | None = None


class NearbyVideoItem(BaseModel):
    video: VideoMini
    place: PlaceMini
    match: MatchInfo
    distance_m: float | None = None


class PlaceVideoMatchItem(BaseModel):
    video: VideoMini
    confidence_status: str
    evidence_sources: list | dict | None = None
    matched_at: datetime