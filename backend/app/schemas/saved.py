from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.place import PlaceResponse
from app.schemas.video import VideoResponse


class SavedVideoResponse(BaseModel):
    saved_id: str
    saved_at: datetime
    video: VideoResponse
    place: PlaceResponse | None = None


class SavedPlaceResponse(BaseModel):
    saved_id: str
    saved_at: datetime
    place: PlaceResponse
    video_count: int = 0
