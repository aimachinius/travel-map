import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import case, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.place import Place
from app.models.saved_place import SavedPlace
from app.models.saved_video import SavedVideo
from app.models.video import Video
from app.models.video_place_match import VideoPlaceMatch
from app.services.discovery_service import DiscoveryService

logger = logging.getLogger(__name__)

# In-memory TTL caches cho các truy vấn bản đồ & chi tiết quán có tần suất đọc cao
_NEARBY_VIDEOS_CACHE: dict[tuple[float, float, float, int, int], tuple[list[dict[str, Any]], float]] = {}
_NEARBY_CACHE_TTL_SEC = 15.0

_SEARCH_PLACES_CACHE: dict[tuple[str, str, int, int], tuple[list[Place], float]] = {}
_SEARCH_CACHE_TTL_SEC = 300.0

_PLACE_DETAIL_CACHE: dict[UUID, tuple[Place, float]] = {}
_PLACE_VIDEOS_CACHE: dict[tuple[UUID, int, int], tuple[list[dict[str, Any]], float]] = {}
_PLACE_DETAIL_TTL_SEC = 30.0


def _expunge_place(db: Session, p: Place) -> Place:
    _ = (
        p.id,
        p.name,
        p.address,
        p.normalized_address,
        p.latitude,
        p.longitude,
        p.description,
        p.category,
        p.source,
        p.source_place_id,
        p.phone_number,
        p.website_url,
        p.is_active,
        p.created_at,
        p.updated_at,
    )
    try:
        db.expunge(p)
    except Exception:
        pass
    return p


def _expunge_video(db: Session, v: Video) -> Video:
    _ = (
        v.id,
        v.platform,
        v.platform_video_id,
        v.video_url,
        v.title,
        v.caption,
        v.duration_seconds,
        v.file_size_mb,
        v.thumbnail_url,
        v.author_name,
        v.transcript,
        v.transcript_text,
        v.created_at,
        v.updated_at,
    )
    try:
        db.expunge(v)
    except Exception:
        pass
    return v


class PlaceService:
    @classmethod
    def get_nearby_videos(
        cls,
        db: Session,
        lat: float,
        lon: float,
        radius_m: float = 2000.0,
        limit: int = 20,
        offset: int = 0,
        current_user_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """
        Luồng 4 Nhánh 1:
        Truy vấn PostGIS ST_DWithin và tính ST_Distance trên kiểu Geography.
        Sắp xếp theo distance_m tăng dần.
        Gắn cờ is_video_saved, is_place_saved nếu user_id có mặt.
        Kích hoạt background discovery nếu số lượng kết quả ít.
        """
        now = time.monotonic()
        cache_key = (round(lat, 4), round(lon, 4), round(radius_m, 1), limit, offset)
        if current_user_id is None:
            cached = _NEARBY_VIDEOS_CACHE.get(cache_key)
            if cached is not None and now < cached[1]:
                return cached[0]

        # Điểm tham chiếu của người dùng WGS 84 (SRID 4326): lon trước, lat sau
        user_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
        user_geog = cast(user_point, Geography)
        place_geog = cast(Place.location, Geography)

        # Tính khoảng cách tính bằng mét
        distance_expr = func.ST_Distance(place_geog, user_geog).label("distance_m")

        query = (
            select(
                Video,
                Place,
                VideoPlaceMatch,
                distance_expr,
            )
            .join(VideoPlaceMatch, VideoPlaceMatch.video_id == Video.id)
            .join(Place, Place.id == VideoPlaceMatch.place_id)
            .where(
                Place.location.isnot(None),
                Place.is_active.is_(True),
                func.ST_DWithin(place_geog, user_geog, radius_m),
            )
            .order_by(distance_expr.asc(), Video.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        results = db.execute(query).all()

        # Kiểm tra danh sách đã lưu nếu người dùng đã đăng nhập
        saved_video_ids: set[UUID] = set()
        saved_place_ids: set[UUID] = set()
        if current_user_id:
            sv_rows = db.scalars(
                select(SavedVideo.video_id).where(SavedVideo.user_id == current_user_id)
            ).all()
            saved_video_ids = set(sv_rows)

            sp_rows = db.scalars(
                select(SavedPlace.place_id).where(SavedPlace.user_id == current_user_id)
            ).all()
            saved_place_ids = set(sp_rows)

        items: list[dict[str, Any]] = []
        for video, place, match, distance_m in results:
            items.append({
                "video": {
                    "id": str(video.id),
                    "platform": video.platform,
                    "platform_video_id": video.platform_video_id,
                    "video_url": video.video_url,
                    "title": video.title,
                    "caption": video.caption,
                    "duration_seconds": video.duration_seconds,
                    "thumbnail_url": video.thumbnail_url,
                    "author_name": video.author_name,
                    "created_at": video.created_at,
                    "is_saved": video.id in saved_video_ids,
                },
                "place": {
                    "id": str(place.id),
                    "name": place.name,
                    "address": place.normalized_address or place.address,
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "category": place.category,
                    "is_saved": place.id in saved_place_ids,
                },
                "match": {
                    "confidence_status": match.confidence_status,
                    "evidence_sources": match.evidence_sources,
                },
                "distance_m": round(float(distance_m), 1) if distance_m is not None else None,
            })

        if current_user_id is None:
            if len(_NEARBY_VIDEOS_CACHE) > 500:
                _NEARBY_VIDEOS_CACHE.clear()
            _NEARBY_VIDEOS_CACHE[cache_key] = (items, now + _NEARBY_CACHE_TTL_SEC)

        return items

    @classmethod
    def search_places(
        cls,
        db: Session,
        query_str: str | None = None,
        category: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Place]:
        now = time.monotonic()
        q_norm = (query_str or "").strip().lower()
        c_norm = (category or "").strip().lower()
        cache_key = (q_norm, c_norm, limit, offset)
        cached = _SEARCH_PLACES_CACHE.get(cache_key)
        if cached is not None and now < cached[1]:
            return cached[0]

        query = select(Place).where(Place.is_active.is_(True))

        if query_str and query_str.strip():
            kw = func.immutable_unaccent_lower(query_str.strip())
            norm_name = func.immutable_unaccent_lower(Place.name)
            norm_addr = func.immutable_unaccent_lower(Place.address)

            query = query.where(
                or_(
                    norm_name.ilike(func.concat("%", kw, "%")),
                    norm_addr.ilike(func.concat("%", kw, "%")),
                    func.similarity(norm_name, kw) >= 0.3,
                )
            )

        if category and category.strip():
            query = query.where(
                func.lower(func.unaccent(Place.category)) == func.lower(func.unaccent(category.strip()))
            )

        places = list(db.scalars(query.order_by(Place.name.asc()).offset(offset).limit(limit)).all())
        for p in places:
            _expunge_place(db, p)

        if len(_SEARCH_PLACES_CACHE) > 1000:
            _SEARCH_PLACES_CACHE.clear()
        _SEARCH_PLACES_CACHE[cache_key] = (places, now + _SEARCH_CACHE_TTL_SEC)
        return places

    @classmethod
    def get_place_detail(cls, db: Session, place_id: UUID) -> Place | None:
        now = time.monotonic()
        cached = _PLACE_DETAIL_CACHE.get(place_id)
        if cached is not None and now < cached[1]:
            return cached[0]

        place = db.get(Place, place_id)
        if place and place.is_active:
            _expunge_place(db, place)
            if len(_PLACE_DETAIL_CACHE) > 2000:
                _PLACE_DETAIL_CACHE.clear()
            _PLACE_DETAIL_CACHE[place_id] = (place, now + _PLACE_DETAIL_TTL_SEC)
            return place
        return None

    @classmethod
    def get_place_videos(
        cls,
        db: Session,
        place_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Luồng 4 Nhánh 2:
        Xem video tại 1 địa điểm.
        Sắp xếp: confidence_status HIGH trước, created_at DESC.
        """
        now = time.monotonic()
        cache_key = (place_id, limit, offset)
        cached = _PLACE_VIDEOS_CACHE.get(cache_key)
        if cached is not None and now < cached[1]:
            return cached[0]

        # Sắp xếp ưu tiên HIGH -> MEDIUM -> LOW (dùng sqlalchemy.case chuẩn thay vì func.case)
        confidence_order = case(
            (VideoPlaceMatch.confidence_status == "HIGH", 1),
            (VideoPlaceMatch.confidence_status == "MEDIUM", 2),
            else_=3,
        )

        query = (
            select(Video, VideoPlaceMatch)
            .join(VideoPlaceMatch, VideoPlaceMatch.video_id == Video.id)
            .where(VideoPlaceMatch.place_id == place_id)
            .order_by(confidence_order.asc(), Video.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        results = db.execute(query).all()
        items = [
            {
                "video": _expunge_video(db, video),
                "confidence_status": match.confidence_status,
                "evidence_sources": match.evidence_sources,
                "matched_at": match.matched_at,
            }
            for video, match in results
        ]
        if len(_PLACE_VIDEOS_CACHE) > 2000:
            _PLACE_VIDEOS_CACHE.clear()
        _PLACE_VIDEOS_CACHE[cache_key] = (items, now + _PLACE_DETAIL_TTL_SEC)
        return items
