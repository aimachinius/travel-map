from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    description: str | None = None
    category: str | None = None
    source: str | None = None
    phone_number: str | None = None
    website_url: str | None = None
    created_at: datetime
    updated_at: datetime