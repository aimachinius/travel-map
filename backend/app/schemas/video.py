from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class VideoSubmitRequest(BaseModel):
    video_url: HttpUrl


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    platform_video_id: str
    video_url: str
    title: str | None
    caption: str | None
    thumbnail_url: str | None
    author_name: str | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    published_at: datetime | None
    created_at: datetime
class VideoSubmitResponse(BaseModel):
    analysis_run_id: UUID
    submitted_url: str
    status: str
    video: VideoResponse
    created_at: datetime

class AnalysisStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    video_id: UUID | None
    submitted_url: str
    status: str
    result_place_id: UUID | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
