"""Administrative Area Coverage & Current Location Address Resolver package.

Calculates polygon coverage of administrative units within a circular radius
and resolves human-readable addresses starting from ward level using OpenStreetMap.
"""

from .cache import TTLCache, query_cache
from .distance import haversine_distance
from .geometry import build_polygon_from_relation, calculate_bbox
from .models import CurrentLocationAddress, DistrictCoverageItem, DistrictCoverageRequest
from .service import (
    DEFAULT_HEADERS,
    DEFAULT_OVERPASS_SERVERS,
    OSM_ATTRIBUTION,
    DistrictCoverageService,
    get_district_coverage,
    resolve_current_address,
)

__all__ = [
    "DistrictCoverageRequest",
    "DistrictCoverageItem",
    "CurrentLocationAddress",
    "DistrictCoverageService",
    "get_district_coverage",
    "resolve_current_address",
    "calculate_bbox",
    "build_polygon_from_relation",
    "haversine_distance",
    "TTLCache",
    "query_cache",
    "OSM_ATTRIBUTION",
    "DEFAULT_OVERPASS_SERVERS",
    "DEFAULT_HEADERS",
]
