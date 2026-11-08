"""Geometry utility functions for OpenStreetMap relations and bounding box calculations."""

import math
from typing import Any, Dict, List, Tuple, Union
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import linemerge, polygonize, unary_union
import shapely


def calculate_bbox(
    lat: float, lon: float, radius_m: float
) -> Tuple[float, float, float, float]:
    """Calculate the bounding box (south, west, north, east) around a point with radius in meters.

    Returns:
        Tuple of (south, west, north, east) rounded to 6 decimal places.
    """
    lat_delta = radius_m / 111320.0
    # Avoid division by zero at the exact poles
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    lon_delta = radius_m / (111320.0 * cos_lat)

    south = max(-90.0, round(lat - lat_delta, 6))
    north = min(90.0, round(lat + lat_delta, 6))
    west = round(lon - lon_delta, 6)
    east = round(lon + lon_delta, 6)

    return (south, west, north, east)


def build_polygon_from_relation(
    members: List[Dict[str, Any]]
) -> Union[Polygon, MultiPolygon]:
    """Assemble OSM relation way members (outer/inner) into a Shapely Polygon or MultiPolygon.

    Handles outer rings, inner holes, disconnected segments, and automatically
    repairs self-intersecting or invalid geometries with shapely.make_valid.

    Args:
        members: List of member dictionaries from an OSM relation with 'geometry' points.

    Returns:
        A valid Shapely Polygon, MultiPolygon, or empty Polygon() if construction is not possible.
    """
    if not members:
        return Polygon()

    outer_lines = []
    inner_lines = []

    for m in members:
        if m.get("type") == "way" and "geometry" in m:
            coords = [(pt["lon"], pt["lat"]) for pt in m["geometry"] if "lon" in pt and "lat" in pt]
            if len(coords) >= 2:
                role = (m.get("role") or "").strip().lower()
                if role == "inner":
                    inner_lines.append(LineString(coords))
                elif role in ("outer", ""):
                    outer_lines.append(LineString(coords))

    if not outer_lines:
        return Polygon()

    # Merge contiguous line segments and polygonize
    merged_outer = linemerge(outer_lines)
    outer_polys = list(polygonize(merged_outer))

    if not outer_polys:
        return Polygon()

    geom = unary_union(outer_polys)

    # Subtract inner holes if any exist
    if inner_lines:
        merged_inner = linemerge(inner_lines)
        inner_polys = list(polygonize(merged_inner))
        if inner_polys:
            geom = geom.difference(unary_union(inner_polys))

    # Repair invalid geometries (e.g. self-intersections or bowtie rings)
    if not geom.is_valid:
        geom = shapely.make_valid(geom)

    return geom

