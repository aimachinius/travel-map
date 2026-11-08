"""Pydantic data models for administrative district coverage and location address."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class DistrictCoverageRequest(BaseModel):
    """Input request schema for administrative coverage calculation."""

    lat: float = Field(
        ...,
        description="Search center latitude in degrees [-90, 90]",
        ge=-90.0,
        le=90.0,
    )
    lon: float = Field(
        ...,
        description="Search center longitude in degrees [-180, 180]",
        ge=-180.0,
        le=180.0,
    )
    radius_m: float = Field(
        default=1500.0,
        description="Search circle radius in meters",
        gt=0.0,
    )
    admin_level: str = Field(
        default="6",
        description="OSM administrative boundary level ('4'=Province/City, '6'=District/County, '8'=Ward/Commune)",
    )

    @field_validator("admin_level")
    @classmethod
    def validate_admin_level(cls, v: str) -> str:
        v_str = str(v).strip()
        if not v_str.isdigit():
            raise ValueError("admin_level must be a numeric string, e.g. '4', '6', '8'")
        return v_str


class DistrictCoverageItem(BaseModel):
    """Output item representing an intersecting administrative unit with coverage area and percentage."""

    osm_id: int = Field(..., description="Unique OpenStreetMap relation or feature ID")
    name: str = Field(..., description="Administrative unit name (e.g. 'Quận Liên Chiểu')")
    admin_level: str = Field(..., description="Administrative level of the unit")
    area_m2: float = Field(..., description="Intersection area in square meters (m²)")
    percentage: float = Field(..., description="Coverage percentage relative to the search circle (0.01% - 100.0%)")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to simple dict."""
        return {
            "osm_id": self.osm_id,
            "name": self.name,
            "admin_level": self.admin_level,
            "area_m2": round(self.area_m2, 1),
            "percentage": round(self.percentage, 2),
        }


class CurrentLocationAddress(BaseModel):
    """Output model for reverse geocoded human-readable address starting from ward level."""

    lat: float = Field(..., description="Latitude of the query point")
    lon: float = Field(..., description="Longitude of the query point")
    address_from_ward: str = Field(
        ...,
        description="Address starting from ward level (e.g. 'Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng, Việt Nam')",
    )
    full_address: str = Field(
        ...,
        description="Full address including road / street name if available",
    )
    ward: Optional[str] = Field(None, description="Normalized Ward or Commune name")
    district: Optional[str] = Field(None, description="Normalized District or County name")
    city: Optional[str] = Field(None, description="Province or Central City name")
    country: str = Field(default="Việt Nam", description="Country name")
    road: Optional[str] = Field(None, description="Street, road, or avenue name if detected")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to simple dict."""
        return {
            "lat": self.lat,
            "lon": self.lon,
            "address_from_ward": self.address_from_ward,
            "full_address": self.full_address,
            "ward": self.ward,
            "district": self.district,
            "city": self.city,
            "country": self.country,
            "road": self.road,
        }
