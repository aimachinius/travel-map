import logging
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.place import Place
from app.models.saved_place import SavedPlace
from app.models.saved_video import SavedVideo
from app.models.video import Video
from app.models.video_place_match import VideoPlaceMatch

logger = logging.getLogger(__name__)


class SavedService:
    # --- Saved Videos ---
    @classmethod
    def _find_video(cls, db: Session, video_id_or_platform_id: str | UUID) -> Video | None:
        if isinstance(video_id_or_platform_id, UUID):
            return db.get(Video, video_id_or_platform_id)

        try:
            uid = UUID(str(video_id_or_platform_id))
            video = db.get(Video, uid)
            if video:
                return video
        except (ValueError, TypeError):
            pass

        return db.scalar(
            select(Video).where(Video.platform_video_id == str(video_id_or_platform_id))
        )

    @classmethod
    def save_video(cls, db: Session, user_id: UUID, video_id: str | UUID) -> tuple[SavedVideo, bool]:
        """
        Lưu video yêu thích (Idempotent).
        Hỗ trợ cả UUID lẫn platform_video_id (chuỗi số TikTok).
        """
        video = cls._find_video(db, video_id)
        if video is None:
            raise ValueError("Video không tồn tại")

        existing = db.scalar(
            select(SavedVideo).where(
                SavedVideo.user_id == user_id,
                SavedVideo.video_id == video.id,
            )
        )
        if existing:
            return existing, False

        saved = SavedVideo(user_id=user_id, video_id=video.id)
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved, True

    @classmethod
    def unsave_video(cls, db: Session, user_id: UUID, video_id: str | UUID) -> bool:
        video = cls._find_video(db, video_id)
        if video is None:
            return False

        saved = db.scalar(
            select(SavedVideo).where(
                SavedVideo.user_id == user_id,
                SavedVideo.video_id == video.id,
            )
        )
        if saved is None:
            return False

        db.delete(saved)
        db.commit()
        return True

    @classmethod
    def get_saved_videos(
        cls,
        db: Session,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Danh sách video đã lưu kèm địa điểm tương ứng, sắp xếp theo created_at DESC.
        """
        query = (
            select(SavedVideo, Video, Place)
            .join(Video, Video.id == SavedVideo.video_id)
            .outerjoin(VideoPlaceMatch, VideoPlaceMatch.video_id == Video.id)
            .outerjoin(Place, Place.id == VideoPlaceMatch.place_id)
            .where(SavedVideo.user_id == user_id)
            .order_by(SavedVideo.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        rows = db.execute(query).all()
        result: list[dict[str, Any]] = []
        for saved, video, place in rows:
            result.append({
                "saved_id": str(saved.id),
                "saved_at": saved.created_at,
                "video": video,
                "place": place,
            })
        return result

    # --- Saved Places ---
    @classmethod
    def save_place(cls, db: Session, user_id: UUID, place_id: UUID) -> tuple[SavedPlace, bool]:
        """
        Lưu địa điểm yêu thích (Idempotent).
        Trả về (saved_place, is_new: bool).
        """
        place = db.get(Place, place_id)
        if place is None or not place.is_active:
            raise ValueError("Địa điểm không tồn tại")

        existing = db.scalar(
            select(SavedPlace).where(
                SavedPlace.user_id == user_id,
                SavedPlace.place_id == place_id,
            )
        )
        if existing:
            return existing, False

        saved = SavedPlace(user_id=user_id, place_id=place_id)
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved, True

    @classmethod
    def unsave_place(cls, db: Session, user_id: UUID, place_id: UUID) -> bool:
        saved = db.scalar(
            select(SavedPlace).where(
                SavedPlace.user_id == user_id,
                SavedPlace.place_id == place_id,
            )
        )
        if saved is None:
            return False

        db.delete(saved)
        db.commit()
        return True

    @classmethod
    def get_saved_places(
        cls,
        db: Session,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Danh sách địa điểm đã lưu kèm tọa độ (lat, lon) và tổng số lượng video review (video_count).
        """
        # Subquery đếm số lượng video cho mỗi quán
        video_count_subq = (
            select(
                VideoPlaceMatch.place_id,
                func.count(VideoPlaceMatch.video_id).label("video_count"),
            )
            .group_by(VideoPlaceMatch.place_id)
            .subquery()
        )

        query = (
            select(
                SavedPlace,
                Place,
                func.coalesce(video_count_subq.c.video_count, 0).label("video_count"),
            )
            .join(Place, Place.id == SavedPlace.place_id)
            .outerjoin(video_count_subq, video_count_subq.c.place_id == Place.id)
            .where(
                SavedPlace.user_id == user_id,
                Place.is_active.is_(True),
            )
            .order_by(SavedPlace.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        rows = db.execute(query).all()
        result: list[dict[str, Any]] = []
        for saved, place, video_count in rows:
            result.append({
                "saved_id": str(saved.id),
                "saved_at": saved.created_at,
                "place": place,
                "video_count": int(video_count),
            })
        return result
