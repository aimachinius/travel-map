import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.discovery_scan import DiscoveryScan
from app.models.video import Video
from app.models.analysis_run import AnalysisRun
from app.services.geocoding_service import ArcGISGeocoder
from app.services.video_service import extract_video_info

logger = logging.getLogger(__name__)


class DiscoveryService:
    @classmethod
    def is_area_recently_scanned(
        cls,
        db: Session,
        lat: float,
        lon: float,
        radius_m: float = 2000.0,
        within_hours: int = 24,
    ) -> bool:
        """
        Kiểm tra xem vùng tọa độ (lat, lon) trong bán kính radius_m đã được quét trong within_hours qua chưa.
        Sử dụng ST_DWithin với Geography để đo mét chính xác.
        """
        since_time = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        target_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

        query = (
            select(DiscoveryScan.id)
            .where(
                DiscoveryScan.scanned_at >= since_time,
                func.ST_DWithin(
                    cast(DiscoveryScan.center_location, Geography),
                    cast(target_point, Geography),
                    radius_m,
                ),
            )
            .limit(1)
        )
        existing = db.scalar(query)
        return existing is not None

    @classmethod
    def generate_keywords(cls, geo_info: dict[str, Any]) -> list[str]:
        """
        Sinh bộ từ khóa tìm kiếm theo mẫu từ địa chỉ nghịch đảo:
        - 'quán ăn gần + POI'
        - 'quán ngon đường + Tên đường'
        - 'ăn vặt + Khu vực'
        """
        keywords: list[str] = []
        poi = geo_info.get("poi")
        street = geo_info.get("street")
        district = geo_info.get("district")
        city = geo_info.get("city")

        if poi and poi.strip():
            keywords.append(f"quán ăn gần {poi.strip()}")
            keywords.append(f"ăn gì gần {poi.strip()}")

        if street and street.strip():
            clean_street = re.sub(r"^(đường|phố|ngõ)\s+", "", street.strip(), flags=re.IGNORECASE)
            keywords.append(f"quán ngon đường {clean_street}")
            keywords.append(f"món ngon {clean_street}")

        area = district or city
        if area and area.strip():
            keywords.append(f"ăn vặt {area.strip()}")
            keywords.append(f"quán ăn ngon {area.strip()}")

        if not keywords:
            keywords = ["quán ăn ngon", "món ngon đường phố"]

        return list(dict.fromkeys(keywords))

    @classmethod
    async def discover_location(
        cls,
        db: Session,
        lat: float,
        lon: float,
        radius_m: float = 2000.0,
        enqueue_callback=None,
    ) -> list[AnalysisRun]:
        """
        Luồng 2: Khám phá video ẩm thực dựa trên vị trí.
        """
        # 1. Kiểm tra cache 24h
        if cls.is_area_recently_scanned(db, lat, lon, radius_m):
            logger.info(f"Vùng ({lat}, {lon}) đã được quét trong 24h qua. Bỏ qua quét mới.")
            return []

        # 2. Reverse geocode để lấy thông tin địa danh
        geo_info = await ArcGISGeocoder.reverse_geocode(lat, lon)
        keywords = cls.generate_keywords(geo_info)

        # 3. Ghi nhận log quét vào discovery_scans
        center_wkt = WKTElement(f"POINT({lon} {lat})", srid=4326)
        scan = DiscoveryScan(
            center_location=center_wkt,
            radius_m=radius_m,
            keywords_generated=keywords,
            videos_found_count=0,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        # 4. Thu thập video theo từ khóa (có thể là scraper thực tế hoặc fallback seed links)
        found_urls = await cls._search_social_videos(keywords)
        new_analysis_runs: list[AnalysisRun] = []

        for video_url in found_urls:
            try:
                platform, platform_video_id = extract_video_info(video_url)
            except ValueError:
                continue

            # Kiểm tra video đã có trong DB chưa
            existing_video = db.scalar(
                select(Video).where(
                    Video.platform == platform,
                    Video.platform_video_id == platform_video_id,
                )
            )

            if existing_video is None:
                video = Video(
                    platform=platform,
                    platform_video_id=platform_video_id,
                    video_url=video_url,
                )
                db.add(video)
                db.flush()
            else:
                video = existing_video

            # Kiểm tra nếu đã có run PENDING hoặc COMPLETED
            existing_run = db.scalar(
                select(AnalysisRun).where(
                    AnalysisRun.video_id == video.id,
                )
            )
            if existing_run is not None:
                continue

            run = AnalysisRun(
                user_id=None,  # Nullable cho SYSTEM_DISCOVERY
                video_id=video.id,
                submitted_url=video_url,
                status="PENDING",
                trigger_source="SYSTEM_DISCOVERY",
                priority=2,
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            new_analysis_runs.append(run)

            if enqueue_callback:
                await enqueue_callback(run.id, priority=2)

        # Cập nhật số lượng video tìm thấy
        scan.videos_found_count = len(new_analysis_runs)
        db.commit()

        logger.info(f"Discovery hoàn tất cho ({lat}, {lon}): tìm thấy {len(new_analysis_runs)} video mới.")
        return new_analysis_runs

    @classmethod
    async def _search_social_videos(cls, keywords: list[str]) -> list[str]:
        """
        Tìm kiếm liên kết TikTok / YouTube Shorts theo từ khóa.
        Sử dụng DuckDuckGo Search nếu khả dụng hoặc fallback an toàn.
        """
        links: list[str] = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for kw in keywords[:3]:
                    query = f"{kw} site:tiktok.com OR site:youtube.com/shorts"
                    results = ddgs.text(query, max_results=5)
                    for r in results:
                        href = r.get("href") or r.get("link")
                        if href and ("tiktok.com" in href or "youtube.com/shorts" in href):
                            links.append(href)
        except Exception as e:
            logger.warning(f"Error querying search engine for discovery: {e}")

        # Loại bỏ trùng lặp
        return list(dict.fromkeys(links))
