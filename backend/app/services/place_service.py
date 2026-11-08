import asyncio
import logging
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
        query = select(Place).where(Place.is_active.is_(True))

        if query_str and query_str.strip():
            kw = func.lower(func.unaccent(query_str.strip()))
            norm_name = func.lower(func.unaccent(Place.name))
            norm_addr = func.lower(func.unaccent(Place.address))

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
        if places:
            place_ids = [p.id for p in places]
            matches = db.execute(
                select(VideoPlaceMatch.place_id, Video.platform_video_id, Video.video_url)
                .join(Video, Video.id == VideoPlaceMatch.video_id)
                .where(VideoPlaceMatch.place_id.in_(place_ids))
                .order_by(Video.created_at.desc())
            ).all()
            video_map = {}
            for p_id, p_vid_id, v_url in matches:
                if p_id not in video_map:
                    video_map[p_id] = (p_vid_id, v_url)

            for p in places:
                if p.id in video_map:
                    p.platform_video_id, p.video_url = video_map[p.id]

        return places

    @classmethod
    def get_place_detail(cls, db: Session, place_id: UUID) -> Place | None:
        place = db.get(Place, place_id)
        if place and place.is_active:
            match = db.execute(
                select(Video.platform_video_id, Video.video_url)
                .join(VideoPlaceMatch, VideoPlaceMatch.video_id == Video.id)
                .where(VideoPlaceMatch.place_id == place_id)
                .order_by(Video.created_at.desc())
                .limit(1)
            ).first()
            if match:
                place.platform_video_id, place.video_url = match
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
        # Sắp xếp ưu tiên HIGH -> MEDIUM -> LOW
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
        return [
            {
                "video": video,
                "confidence_status": match.confidence_status,
                "evidence_sources": match.evidence_sources,
                "matched_at": match.matched_at,
            }
            for video, match in results
        ]
