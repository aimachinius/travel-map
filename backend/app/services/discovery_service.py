"""Discovery Service orchestrating location-based video scraping and queue ingestion."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, List, Optional, Set
from uuid import UUID

from geoalchemy2 import Geography
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.discovery_scan import DiscoveryScan
from app.models.video import Video
from app.services.area import get_district_coverage, resolve_current_address
from app.services.crawler import crawl_tiktok_links_async
from app.services.discovery import generate_orthogonal_keywords
from app.services.video_service import extract_video_info

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Orchestrates location-based video discovery, 24h deduplication, scraping, and ingestion."""

    @classmethod
    def is_area_recently_scanned(
        cls,
        db: Session,
        lat: float,
        lon: float,
        threshold_distance_m: float = 1000.0,
        within_hours: int = 24,
    ) -> bool:
        """Check if any discovery scan occurred within threshold_distance_m (<=1km) in the last within_hours.

        Uses ST_DWithin with Geography to accurately measure distance in meters.
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
                    threshold_distance_m,
                ),
            )
            .limit(1)
        )
        existing = db.scalar(query)
        return existing is not None

    @classmethod
    def get_recent_crawled_keywords(
        cls,
        db: Session,
        within_hours: int = 24,
    ) -> Set[str]:
        """Retrieve set of all keywords used in discovery scans within the last within_hours."""
        since_time = datetime.now(timezone.utc) - timedelta(hours=within_hours)
        query = select(DiscoveryScan.keywords_generated).where(
            DiscoveryScan.scanned_at >= since_time,
            DiscoveryScan.keywords_generated.isnot(None),
        )
        results = db.scalars(query).all()

        recent_keywords: Set[str] = set()
        for kw_entry in results:
            if isinstance(kw_entry, list):
                for kw in kw_entry:
                    if kw and isinstance(kw, str):
                        recent_keywords.add(kw.strip().lower())
            elif isinstance(kw_entry, dict):
                for kw in kw_entry.values():
                    if kw and isinstance(kw, str):
                        recent_keywords.add(kw.strip().lower())
        return recent_keywords

    @classmethod
    async def discover_location(
        cls,
        db: Session,
        lat: float,
        lon: float,
        radius_m: float = 2000.0,
        enqueue_callback: Optional[Callable[[UUID, int], Coroutine[Any, Any, None]]] = None,
        force: bool = False,
    ) -> List[AnalysisRun]:
        """Execute the full 4-step Discovery Pipeline for coordinate (lat, lon).

        Step 0: Check 1km spatial threshold within 24h (skipped if force=True).
        Step 1: Resolve administrative address (ward, district, city) & district coverage %.
        Step 2: Generate orthogonal keywords (food, cafe, snack) & filter 24h duplicates.
        Step 3: Crawl TikTok video links via Playwright with anti-bot precautions.
        Step 4: Save videos & create PENDING AnalysisRuns (priority 2), push to Redis queue.
        """
        logger.info(
            f"\n======================================================\n"
            f"[DISCOVERY PIPELINE] KHỞI ĐỘNG TIẾN TRÌNH KHÁM PHÁ VỊ TRÍ\n"
            f"Tọa độ: ({lat}, {lon}) | Bán kính quét: {radius_m}m | Force: {force}\n"
            f"======================================================"
        )

        # -------------------------------------------------------------------------
        # BƯỚC 0: KIỂM TRA CHỐNG QUÉT LẶP (1KM SPATIAL THRESHOLD TRONG 24H)
        # -------------------------------------------------------------------------
        logger.info("[DISCOVERY PIPELINE][BƯỚC 0/4] Kiểm tra chống quét lặp không gian (1km trong 24h)...")
        if not force and cls.is_area_recently_scanned(db, lat, lon, threshold_distance_m=1000.0, within_hours=24):
            logger.info(
                f"[DISCOVERY PIPELINE][BƯỚC 0/4] Vị trí ({lat}, {lon}) nằm trong bán kính <= 1000m "
                f"so với một điểm đã được quét trong 24 giờ qua. Bỏ qua quét mới, trả về dữ liệu sẵn có."
            )
            return []
        logger.info("[DISCOVERY PIPELINE][BƯỚC 0/4] Vị trí hợp lệ, chưa quét trong 24h qua. Tiếp tục xử lý.")

        # -------------------------------------------------------------------------
        # BƯỚC 1: LẤY ĐỊA DANH HÀNH CHÍNH & TÍNH ĐỘ PHỦ KHU VỰC
        # -------------------------------------------------------------------------
        logger.info("[DISCOVERY PIPELINE][BƯỚC 1/4] Phân giải địa chỉ hành chính & tính độ phủ khu vực...")
        current_address = await asyncio.to_thread(resolve_current_address, lat, lon)
        ward_text = current_address.get("ward") or "N/A"
        district_text = current_address.get("district") or "N/A"
        city_text = current_address.get("city") or "N/A"
        full_addr = current_address.get("full_address") or current_address.get("address_from_ward")

        logger.info(
            f"[DISCOVERY PIPELINE][BƯỚC 1/4] Kết quả phân giải địa chỉ:\n"
            f"  - Phường/Xã: {ward_text}\n"
            f"  - Quận/Huyện: {district_text}\n"
            f"  - Tỉnh/Thành phố: {city_text}\n"
            f"  - Chuỗi địa chỉ đầy đủ: {full_addr}"
        )

        coverage_items = await asyncio.to_thread(
            get_district_coverage,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            admin_level="6",
        )
        if coverage_items:
            coverage_log = ", ".join(f"{it['name']} ({it['percentage']}%)" for it in coverage_items)
            logger.info(f"[DISCOVERY PIPELINE][BƯỚC 1/4] Độ phủ quận/huyện trong bán kính {radius_m}m: {coverage_log}")
        else:
            logger.info(f"[DISCOVERY PIPELINE][BƯỚC 1/4] Không tìm thấy ranh giới đa giác OSM, sử dụng đơn vị địa chỉ.")

        # -------------------------------------------------------------------------
        # BƯỚC 2: SINH BỘ TỪ KHÓA ẨM THỰC PHÂN TÁCH & LỌC TRÙNG 24H
        # -------------------------------------------------------------------------
        logger.info("[DISCOVERY PIPELINE][BƯỚC 2/4] Sinh bộ từ khóa ẩm thực phân tách (Orthogonal Keywords)...")
        raw_keywords = generate_orthogonal_keywords(
            current_address=current_address,
            coverage_items=coverage_items,
            max_keywords=6,
        )
        logger.info(f"[DISCOVERY PIPELINE][BƯỚC 2/4] Danh sách từ khóa vừa sinh ({len(raw_keywords)} từ khóa):")
        for idx, kw in enumerate(raw_keywords, 1):
            logger.info(f"    [{idx}] {kw}")

        # Lọc trùng từ khóa trong vòng 24h
        recent_keywords = cls.get_recent_crawled_keywords(db, within_hours=24)
        keywords_to_crawl: List[str] = []
        skipped_keywords: List[str] = []

        for kw in raw_keywords:
            if kw.lower() in recent_keywords:
                skipped_keywords.append(kw)
            else:
                keywords_to_crawl.append(kw)

        if skipped_keywords:
            logger.info(
                f"[DISCOVERY PIPELINE][BƯỚC 2/4] Đã loại bỏ {len(skipped_keywords)} từ khóa đã cào trong 24h qua: "
                f"{skipped_keywords}"
            )

        if not keywords_to_crawl:
            logger.info(
                "[DISCOVERY PIPELINE][BƯỚC 2/4] Toàn bộ từ khóa sinh ra đều đã được cào trong vòng 24h qua! "
                "Kết thúc tiến trình cào để bảo vệ tài nguyên hệ thống."
            )
            return []

        logger.info(
            f"[DISCOVERY PIPELINE][BƯỚC 2/4] Số từ khóa còn lại tiến hành cào ({len(keywords_to_crawl)} từ khóa): "
            f"{keywords_to_crawl}"
        )

        # Ghi nhận bản ghi vùng quét mới vào discovery_scans
        center_wkt = WKTElement(f"POINT({lon} {lat})", srid=4326)
        scan = DiscoveryScan(
            center_location=center_wkt,
            radius_m=radius_m,
            keywords_generated=keywords_to_crawl,
            videos_found_count=0,
        )
        try:
            db.add(scan)
            db.commit()
            db.refresh(scan)
        except Exception as e:
            db.rollback()
            logger.warning(f"[DISCOVERY PIPELINE][BƯỚC 2/4] Lỗi ghi nhận DiscoveryScan: {e}")
            raise

        # -------------------------------------------------------------------------
        # BƯỚC 3 & 4: CÀO TIKTOK & STREAMING INGESTION (ĐẨY NGAY SANG SERVER AI)
        # -------------------------------------------------------------------------
        logger.info(
            f"[DISCOVERY PIPELINE][BƯỚC 3/4] Bắt đầu cào link video TikTok & Streaming Ingestion "
            f"cho {len(keywords_to_crawl)} từ khóa..."
        )
        seen_urls_in_session: Set[str] = set()
        new_analysis_runs: List[AnalysisRun] = []

        for idx, keyword in enumerate(keywords_to_crawl, 1):
            logger.info(f"[DISCOVERY PIPELINE][BƯỚC 3/4] ({idx}/{len(keywords_to_crawl)}) Cào từ khóa: '{keyword}'...")
            kw_links: List[str] = []
            try:
                kw_links = await crawl_tiktok_links_async(
                    query=keyword,
                    scroll_count=3,
                    headless=True,
                    verbose=False,
                )
                logger.info(f"[DISCOVERY PIPELINE][BƯỚC 3/4] -> Từ khóa '{keyword}' cào được {len(kw_links)} link video.")
            except Exception as e:
                logger.warning(f"[DISCOVERY PIPELINE][BƯỚC 3/4] -> Lỗi cào từ khóa '{keyword}': {e}")

            # Xử lý Streaming: Khử trùng, lưu DB và đẩy ngay sang Server AI cho từ khóa này
            kw_new_runs_count = 0
            for video_url in kw_links:
                clean_url = video_url.split("?")[0].strip()
                if not clean_url or clean_url in seen_urls_in_session:
                    continue
                seen_urls_in_session.add(clean_url)

                try:
                    platform, platform_video_id = extract_video_info(clean_url)
                except ValueError as e:
                    logger.debug(f"[DISCOVERY PIPELINE][STREAMING] Bỏ qua URL không hợp lệ: {clean_url} ({e})")
                    continue

                try:
                    # Kiểm tra video đã có trong database chưa
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
                            video_url=clean_url,
                        )
                        db.add(video)
                        db.flush()
                    else:
                        video = existing_video

                    # Kiểm tra nếu đã có run PENDING, PROCESSING hoặc COMPLETED
                    existing_run = db.scalar(
                        select(AnalysisRun.id).where(
                            AnalysisRun.video_id == video.id,
                            AnalysisRun.status.in_(["PENDING", "PROCESSING", "COMPLETED"]),
                        ).limit(1)
                    )
                    if existing_run is not None:
                        logger.debug(f"[DISCOVERY PIPELINE][STREAMING] Video {platform_video_id} đã có AnalysisRun. Bỏ qua.")
                        continue

                    # Tạo bản ghi AnalysisRun mới với priority = 2, trigger_source = 'SYSTEM_DISCOVERY'
                    run = AnalysisRun(
                        user_id=None,  # Nullable cho tác vụ do hệ thống tự quét
                        video_id=video.id,
                        submitted_url=clean_url,
                        status="PENDING",
                        trigger_source="SYSTEM_DISCOVERY",
                        priority=2,
                    )
                    db.add(run)
                    db.commit()
                    db.refresh(run)

                    new_analysis_runs.append(run)
                    kw_new_runs_count += 1

                    # ĐẨY NGAY VÀO REDIS: AI Server worker sẽ bốc task và phân tích song song ngay lập tức!
                    if enqueue_callback:
                        try:
                            await enqueue_callback(run.id, priority=2)
                        except Exception as e:
                            logger.warning(f"[DISCOVERY PIPELINE][STREAMING] Lỗi đẩy task vào hàng đợi Redis: {e}")

                except Exception as e:
                    db.rollback()
                    logger.warning(f"[DISCOVERY PIPELINE][STREAMING] Lỗi lưu video {clean_url}: {e}")

            if kw_new_runs_count > 0:
                logger.info(
                    f"[DISCOVERY PIPELINE][STREAMING] -> Đã đẩy ngay {kw_new_runs_count} video mới của từ khóa '{keyword}' "
                    f"vào Redis queue:low_priority để Server AI phân tích song song!"
                )
            else:
                logger.info(
                    f"[DISCOVERY PIPELINE][STREAMING] -> Không có video mới cần phân tích cho từ khóa '{keyword}'."
                )

            # Nghỉ 5 giây giữa các từ khóa để tránh rate-limit (tuân thủ mục 2.3 README)
            if idx < len(keywords_to_crawl):
                await asyncio.sleep(5.0)

        # Cập nhật số lượng video tìm thấy lũy kế vào discovery_scans
        try:
            scan.videos_found_count = len(new_analysis_runs)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"[DISCOVERY PIPELINE] Lỗi cập nhật scan count: {e}")

        logger.info(
            f"\n======================================================\n"
            f"[DISCOVERY PIPELINE] HOÀN TẤT QUY TRÌNH CHO ({lat}, {lon})\n"
            f"Tổng số link duyệt: {len(seen_urls_in_session)} | Tạo mới & đẩy AI Server: {len(new_analysis_runs)} AnalysisRuns ưu tiên 2.\n"
            f"======================================================\n"
        )
        return new_analysis_runs
