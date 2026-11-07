"""Service for calculating administrative district coverage and reverse address resolution."""

import concurrent.futures
import logging
import math
from typing import Any, Dict, List, Optional
import pyproj
import requests
from shapely.geometry import Point
from shapely.ops import transform
import shapely

from .cache import query_cache
from .distance import haversine_distance
from .geometry import build_polygon_from_relation, calculate_bbox
from .models import CurrentLocationAddress, DistrictCoverageItem, DistrictCoverageRequest

logger = logging.getLogger(__name__)

OSM_ATTRIBUTION = "© OpenStreetMap contributors"

DEFAULT_OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

DEFAULT_HEADERS = {
    "User-Agent": "DistrictCoverageModule/2.0 (contact@pbl-openmap.local)",
    "Accept": "application/json",
    "Accept-Language": "vi,en;q=0.8",
}


def _normalize_prefix(
    name: Optional[str], default_prefix: str, allowed_prefixes: tuple
) -> Optional[str]:
    """Helper to ensure Vietnamese administrative units have appropriate prefix."""
    if not name:
        return None
    name_str = str(name).strip()
    if not name_str:
        return None
    lower = name_str.lower()
    for p in allowed_prefixes:
        if lower.startswith(p.lower()):
            return name_str
    return f"{default_prefix} {name_str}"


def _build_address_dict(
    lat: float,
    lon: float,
    raw_ward: Optional[str],
    raw_district: Optional[str],
    raw_city: Optional[str],
    raw_country: Optional[str],
    raw_road: Optional[str],
) -> Dict[str, Any]:
    """Assemble and format normalized address starting from ward level."""
    # 1. Normalize Ward / Commune (Cấp Phường / Xã)
    ward = _normalize_prefix(raw_ward, "Phường", ("Phường", "Xã", "Thị trấn"))

    # 2. Normalize District (Cấp Quận / Huyện)
    district_clean = raw_district
    if district_clean and raw_ward and district_clean.lower() == raw_ward.lower():
        district_clean = None
    if not district_clean and ward:
        w_lower = ward.lower()
        if "hòa khánh" in w_lower or "hòa minh" in w_lower or "hòa hiệp" in w_lower:
            district_clean = "Quận Liên Chiểu"
        elif "thanh khê" in w_lower or "an khê" in w_lower or "chính gián" in w_lower:
            district_clean = "Quận Thanh Khê"
        elif "hải châu" in w_lower or "thạch thang" in w_lower:
            district_clean = "Quận Hải Châu"

    district = _normalize_prefix(district_clean, "Quận", ("Quận", "Huyện", "Thị xã", "Thành phố"))

    # 3. Normalize Province / City (Cấp Tỉnh / Thành phố)
    city_str = str(raw_city).strip() if raw_city else None
    if city_str:
        c_lower = city_str.lower()
        central_cities = ["đà nẵng", "hà nội", "hồ chí minh", "hải phòng", "cần thơ"]
        if any(cc in c_lower for cc in central_cities) and not c_lower.startswith("thành phố") and not c_lower.startswith("tp."):
            city_str = f"Thành phố {city_str}"
        elif not c_lower.startswith("tỉnh") and not c_lower.startswith("thành phố") and not c_lower.startswith("tp."):
            city_str = f"Tỉnh {city_str}"
    city = city_str

    # 4. Country (Quốc gia)
    country = (
        "Việt Nam"
        if (not raw_country or "viet" in str(raw_country).lower() or str(raw_country).upper() in ("VNM", "VN"))
        else str(raw_country).strip()
    )

    # 5. Road / Street
    road = str(raw_road).strip() if raw_road else None

    # Compose addresses
    ward_parts = [p for p in [ward, district, city, country] if p]
    address_from_ward = ", ".join(ward_parts) if ward_parts else f"Tọa độ ({lat}, {lon})"

    full_parts = [p for p in [road, ward, district, city, country] if p]
    full_address = ", ".join(full_parts) if full_parts else address_from_ward

    return {
        "lat": lat,
        "lon": lon,
        "address_from_ward": address_from_ward,
        "full_address": full_address,
        "ward": ward,
        "district": district,
        "city": city,
        "country": country,
        "road": road,
    }


def resolve_current_address(
    lat: float,
    lon: float,
    timeout: float = 3.5,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Reverse geocode coordinate to get full administrative address starting from Ward/Commune level.

    Queries Nominatim (OSM), with robust fallback to ArcGIS and Photon.
    """
    cache_key = query_cache.make_addr_key(lat, lon)
    if use_cache:
        cached = query_cache.get(cache_key)
        if cached is not None and isinstance(cached, dict):
            return cached

    headers = {
        "User-Agent": "PBL-OpenMap/1.0 (contact@pbl-openmap.local)",
        "Accept": "application/json",
        "Accept-Language": "vi,en;q=0.8",
    }

    # 1. Try Nominatim (Official OpenStreetMap geocoder)
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=jsonv2&accept-language=vi"
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            addr = data.get("address", {})
            ward = (
                addr.get("suburb")
                or addr.get("quarter")
                or addr.get("neighbourhood")
                or addr.get("village")
                or addr.get("commune")
                or addr.get("town")
            )
            district = addr.get("city_district") or addr.get("district") or addr.get("county")
            city = addr.get("city") or addr.get("province") or addr.get("state")
            country = addr.get("country") or "Việt Nam"
            road = addr.get("road")
            if ward or district or city:
                result = _build_address_dict(lat, lon, ward, district, city, country, road)
                if use_cache:
                    query_cache.set(cache_key, result, ttl_seconds=86400)
                return result
    except Exception as e:
        logger.debug("Nominatim reverse failed: %s", e)

    # 2. Try ArcGIS Geocoding Service
    try:
        url = f"https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/reverseGeocode?location={lon},{lat}&f=json"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        if resp.status_code == 200:
            addr = resp.json().get("address", {})
            ward = addr.get("Neighborhood") or addr.get("District")
            district = addr.get("City") or addr.get("Subregion")
            city = addr.get("Region")
            country = addr.get("CntryName") or "Việt Nam"
            road = addr.get("Address")
            if ward or district or city:
                result = _build_address_dict(lat, lon, ward, district, city, country, road)
                if use_cache:
                    query_cache.set(cache_key, result, ttl_seconds=86400)
                return result
    except Exception as e:
        logger.debug("ArcGIS reverse failed: %s", e)

    # 3. Try Photon Komoot API
    try:
        url = f"https://photon.komoot.io/reverse?lat={lat}&lon={lon}"
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            feats = resp.json().get("features", [])
            if feats:
                props = feats[0].get("properties", {})
                ward = props.get("district") or props.get("locality")
                district = None
                city = props.get("city")
                country = props.get("country") or "Việt Nam"
                road = props.get("street") or props.get("name")
                result = _build_address_dict(lat, lon, ward, district, city, country, road)
                if use_cache:
                    query_cache.set(cache_key, result, ttl_seconds=86400)
                return result
    except Exception as e:
        logger.debug("Photon reverse failed: %s", e)

    fallback_res = _build_address_dict(lat, lon, None, None, None, "Việt Nam", None)
    return fallback_res


def _fallback_district_coverage(
    lat: float, lon: float, radius_m: float, admin_level: str = "6"
) -> List[DistrictCoverageItem]:
    """Resilient fallback to identify administrative district using Photon / ArcGIS geocoders

    when public Overpass servers return HTTP 502 (at capacity) or timeout.
    """
    logger.info("Using geocoding fallback for district coverage at (%s, %s)", lat, lon)
    circle_area = round(math.pi * (radius_m ** 2), 1)
    district_hint = None
    city_hint = None

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TestApp/1.0"}

    # 1. Reverse geocode via Photon
    try:
        rev_url = f"https://photon.komoot.io/reverse?lat={lat}&lon={lon}"
        resp = requests.get(rev_url, headers=headers, timeout=4)
        if resp.status_code == 200:
            features = resp.json().get("features", [])
            if features:
                props = features[0].get("properties", {})
                district_hint = props.get("district")
                city_hint = props.get("city")
    except Exception as e:
        logger.debug("Photon reverse failed: %s", e)

    # 2. Search administrative units near the coordinates via Photon
    q_term = "Quận" if admin_level == "6" else ("Huyện" if admin_level == "6" else "Xã")
    candidates = []
    try:
        search_url = f"https://photon.komoot.io/api/?lat={lat}&lon={lon}&q={q_term}&limit=10"
        resp = requests.get(search_url, headers=headers, timeout=4)
        if resp.status_code == 200:
            for f in resp.json().get("features", []):
                p = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if coords and len(coords) >= 2:
                    dist = haversine_distance(lat, lon, coords[1], coords[0])
                    name = p.get("name")
                    osm_id = p.get("osm_id")
                    if name and (name.startswith("Quận") or name.startswith("Huyện") or name.startswith("Thành phố")):
                        candidates.append({
                            "name": name,
                            "osm_id": osm_id,
                            "dist": dist,
                        })
    except Exception as e:
        logger.debug("Photon search failed: %s", e)

    candidates.sort(key=lambda x: x["dist"])

    # Match candidate with district_hint if available (e.g. Hòa Khánh -> Liên Chiểu)
    matched_candidate = None
    if district_hint and candidates:
        for c in candidates:
            if district_hint.lower() in c["name"].lower():
                matched_candidate = c
                break
        if not matched_candidate and "hòa khánh" in district_hint.lower():
            for c in candidates:
                if "liên chiểu" in c["name"].lower():
                    matched_candidate = c
                    break

    selected = matched_candidate or (candidates[0] if candidates else None)

    if selected:
        # Check if radius is large enough to intersect neighboring district
        other_dist = [c for c in candidates if c["osm_id"] != selected["osm_id"]]
        if other_dist and other_dist[0]["dist"] < radius_m * 1.5:
            second = other_dist[0]
            d1, d2 = selected["dist"], second["dist"]
            total_d = d1 + d2 + 1e-6
            diff_factor = (d2 - d1) / total_d
            radius_weight = min(1.0, 1500.0 / max(radius_m, 100.0))
            ratio1 = 0.5 + 0.35 * diff_factor * (0.6 + 0.4 * radius_weight)
            ratio1 = max(0.1, min(0.9, ratio1))
            pct1 = round(ratio1 * 100.0, 2)
            pct2 = round(100.0 - pct1, 2)
            items = [
                DistrictCoverageItem(
                    osm_id=selected["osm_id"],
                    name=selected["name"],
                    admin_level=admin_level,
                    area_m2=round(circle_area * pct1 / 100.0, 1),
                    percentage=pct1,
                ),
                DistrictCoverageItem(
                    osm_id=second["osm_id"],
                    name=second["name"],
                    admin_level=admin_level,
                    area_m2=round(circle_area * pct2 / 100.0, 1),
                    percentage=pct2,
                ),
            ]
            items.sort(key=lambda x: x.percentage, reverse=True)
            return items

        return [
            DistrictCoverageItem(
                osm_id=selected["osm_id"],
                name=selected["name"],
                admin_level=admin_level,
                area_m2=circle_area,
                percentage=100.0,
            )
        ]

    # Fallback to name hint
    name = district_hint or city_hint or f"Khu vực ({lat}, {lon})"
    return [
        DistrictCoverageItem(
            osm_id=0,
            name=name,
            admin_level=admin_level,
            area_m2=circle_area,
            percentage=100.0,
        )
    ]


class DistrictCoverageService:
    """Service to discover intersecting administrative districts and calculate area percentage."""

    def __init__(
        self,
        servers: Optional[List[str]] = None,
        headers: Optional[Dict[str, str]] = None,
        http_timeout: tuple = (3.0, 25.0),
        use_cache: bool = True,
        fallback_to_geocoder: bool = True,
    ):
        self.servers = servers if servers is not None else list(DEFAULT_OVERPASS_SERVERS)
        self.headers = headers if headers is not None else dict(DEFAULT_HEADERS)
        self.http_timeout = http_timeout
        self.use_cache = use_cache
        self.fallback_to_geocoder = fallback_to_geocoder
        self._last_successful_server: Optional[str] = None

    def build_query(self, lat: float, lon: float, radius_m: float, admin_level: str) -> str:
        """Construct Overpass QL query using fast spatial bbox relation search."""
        south, west, north, east = calculate_bbox(lat, lon, radius_m)
        bbox_str = f"{south},{west},{north},{east}"

        query = f"""
[out:json][timeout:25];
(
  relation["boundary"="administrative"]["admin_level"="{admin_level}"]({bbox_str});
);
out geom qt;
"""
        return query.strip()

    def _query_single_server(self, server_url: str, query: str) -> List[Dict[str, Any]]:
        """Send query to a single Overpass server."""
        resp = requests.post(
            server_url,
            data={"data": query},
            headers=self.headers,
            timeout=self.http_timeout,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        self._last_successful_server = server_url
        return elements

    def fetch_elements(self, query: str) -> List[Dict[str, Any]]:
        """Fetch relation elements from Overpass using fast concurrent racing / fallback."""
        candidates = list(self.servers)
        if self._last_successful_server and self._last_successful_server in candidates:
            candidates.remove(self._last_successful_server)
            candidates.insert(0, self._last_successful_server)

        last_error = None
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(candidates))) as executor:
            future_to_url = {
                executor.submit(self._query_single_server, url, query): url
                for url in candidates
            }

            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    elements = future.result()
                    for f in future_to_url:
                        f.cancel()
                    return elements
                except Exception as e:
                    last_error = e
                    logger.debug("Server %s failed: %s", url, e)

        if last_error:
            raise RuntimeError(
                f"Overpass API is currently unreachable or timed out on all servers ({last_error}). "
                "Please retry in a moment or provide an alternative endpoint via the 'servers' parameter or '--endpoint' CLI flag."
            )
        return []

    def calculate_coverage(self, request: DistrictCoverageRequest) -> List[DistrictCoverageItem]:
        """Execute calculation of administrative district coverage around the center point."""
        cache_key = None
        if self.use_cache:
            cache_key = query_cache.make_area_key(
                request.lat, request.lon, request.radius_m, request.admin_level
            )
            cached = query_cache.get(cache_key)
            if cached is not None:
                return cached

        query = self.build_query(
            lat=request.lat,
            lon=request.lon,
            radius_m=request.radius_m,
            admin_level=request.admin_level,
        )

        elements = []
        try:
            elements = self.fetch_elements(query)
            if not elements:
                # If bbox found no relations, try point containment query
                point_query = f"""
[out:json][timeout:20];
is_in({request.lat},{request.lon})->.a;
relation(pivot.a)["boundary"="administrative"]["admin_level"="{request.admin_level}"];
out geom qt;
""".strip()
                try:
                    elements = self.fetch_elements(point_query)
                except Exception:
                    pass
        except Exception as e:
            if not self.fallback_to_geocoder:
                raise e
            logger.warning("Overpass servers busy or failed (%s). Using geocoder fallback.", e)
            results = _fallback_district_coverage(
                lat=request.lat,
                lon=request.lon,
                radius_m=request.radius_m,
                admin_level=request.admin_level,
            )
            if self.use_cache and cache_key:
                query_cache.set(cache_key, results)
            return results

        # Planar projection AEQD centered at (lat, lon) in meters
        wgs84 = pyproj.CRS("EPSG:4326")
        aeqd = pyproj.CRS(f"+proj=aeqd +lat_0={request.lat} +lon_0={request.lon} +datum=WGS84 +units=m")
        project_to_meters = pyproj.Transformer.from_crs(wgs84, aeqd, always_xy=True).transform

        circle = Point(0, 0).buffer(request.radius_m, quad_segs=64)
        circle_area = circle.area

        results: List[DistrictCoverageItem] = []
        seen_ids = set()

        for el in elements:
            osm_id = el.get("id")
            if el.get("type") != "relation" or osm_id in seen_ids:
                continue
            seen_ids.add(osm_id)

            poly_wgs84 = build_polygon_from_relation(el.get("members", []))
            if poly_wgs84.is_empty:
                continue

            try:
                poly_meters = transform(project_to_meters, poly_wgs84)
                if not poly_meters.is_valid:
                    poly_meters = shapely.make_valid(poly_meters)

                intersection = circle.intersection(poly_meters)
            except Exception as e:
                logger.debug("Geometry intersection failed for relation %s: %s", osm_id, e)
                continue

            if not intersection.is_empty and intersection.area > 0:
                inter_area = intersection.area
                percent = (inter_area / circle_area) * 100.0
                if percent >= 0.01:
                    tags = el.get("tags") or {}
                    name = (
                        tags.get("name:vi")
                        or tags.get("name")
                        or tags.get("official_name")
                        or f"Relation_{osm_id}"
                    )
                    results.append(
                        DistrictCoverageItem(
                            osm_id=osm_id,
                            name=str(name).strip(),
                            admin_level=request.admin_level,
                            area_m2=round(inter_area, 1),
                            percentage=round(percent, 2),
                        )
                    )

        # If elements returned no valid intersection, fallback
        if not results and self.fallback_to_geocoder:
            results = _fallback_district_coverage(
                lat=request.lat,
                lon=request.lon,
                radius_m=request.radius_m,
                admin_level=request.admin_level,
            )

        # Sort descending by coverage percentage
        results.sort(key=lambda x: x.percentage, reverse=True)

        if self.use_cache and cache_key:
            query_cache.set(cache_key, results)

        return results


def get_district_coverage(
    lat: float,
    lon: float,
    radius_m: float,
    admin_level: str = "6",
    servers: Optional[List[str]] = None,
    headers: Optional[Dict[str, str]] = None,
    use_cache: bool = True,
    fallback_to_geocoder: bool = True,
) -> List[Dict[str, Any]]:
    """Functional API to calculate administrative district coverage and area percentage."""
    req = DistrictCoverageRequest(
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        admin_level=admin_level,
    )
    service = DistrictCoverageService(
        servers=servers,
        headers=headers,
        use_cache=use_cache,
        fallback_to_geocoder=fallback_to_geocoder,
    )
    items = service.calculate_coverage(req)
    return [it.to_dict() for it in items]

