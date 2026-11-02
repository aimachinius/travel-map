from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, HttpUrl


class VideoSubmitRequest(BaseModel):
    video_url: HttpUrl
    force_reanalyze: bool = False


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    platform: str
    platform_video_id: str
    video_url: str
    title: str | None = None
    caption: str | None = None
    duration_seconds: float | None = None
    file_size_mb: float | None = None
    transcript: str | None = None
    transcript_text: str | None = None
    thumbnail_url: str | None = None
    author_name: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    published_at: datetime | None = None
    created_at: datetime


class VideoSubmitResponse(BaseModel):
    analysis_run_id: UUID
    video_id: UUID
    submitted_url: str
    status: str
    cached: bool = False
    created_at: datetime


class AnalysisStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    video_id: UUID | None = None
    submitted_url: str
    status: str
    trigger_source: str = "USER_SUBMIT"
    priority: int = 1
    result_place_id: UUID | None = None
    keyframes_data: list | dict | None = None
    ocr_data: list | dict | None = None
    execution_metrics: dict | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
