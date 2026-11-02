import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from geoalchemy2.elements import WKTElement
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.websocket_manager import websocket_manager
from app.models.analysis_run import AnalysisRun
from app.models.place import Place
from app.models.video import Video
from app.models.video_place_match import VideoPlaceMatch
from app.services.geocoding_service import ArcGISGeocoder

logger = logging.getLogger(__name__)

# Redis queues
QUEUE_HIGH = "queue:high_priority"
QUEUE_LOW = "queue:low_priority"

# In-memory fallback queue for local development / testing without Redis running
_in_memory_high_queue: asyncio.Queue = asyncio.Queue()
_in_memory_low_queue: asyncio.Queue = asyncio.Queue()


def get_redis_client():
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return client
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}. Falling back to in-memory queues.")
        return None


async def enqueue_analysis(analysis_run_id: UUID | str, priority: int = 1) -> None:
    """
    Đẩy task phân tích vào Redis Queue:
    - Priority 1 -> queue:high_priority
    - Priority 2 -> queue:low_priority
    """
    run_id_str = str(analysis_run_id)
    redis_client = get_redis_client()
    queue_name = QUEUE_HIGH if priority == 1 else QUEUE_LOW

    if redis_client:
        try:
            await redis_client.rpush(queue_name, run_id_str)
            logger.info(f"Enqueued {run_id_str} to Redis {queue_name}")
            await redis_client.aclose()
            return
        except Exception as e:
            logger.warning(f"Redis rpush error: {e}. Using in-memory fallback.")

    # Fallback in-memory
    if priority == 1:
        await _in_memory_high_queue.put(run_id_str)
    else:
        await _in_memory_low_queue.put(run_id_str)
    logger.info(f"Enqueued {run_id_str} to in-memory queue (priority {priority})")


async def dequeue_next_analysis() -> tuple[str | None, int]:
    """
    Strict Priority Polling:
    Worker luôn kiểm tra queue:high_priority trước.
    Chỉ khi rỗng mới rút từ queue:low_priority.
    """
    redis_client = get_redis_client()
    if redis_client:
        try:
            # 1. Check high priority
            item = await redis_client.lpop(QUEUE_HIGH)
            if item:
                await redis_client.aclose()
                return item, 1

            # 2. Check low priority
            item = await redis_client.lpop(QUEUE_LOW)
            if item:
                await redis_client.aclose()
                return item, 2

            await redis_client.aclose()
        except Exception as e:
            logger.warning(f"Redis lpop error: {e}. Falling back to in-memory.")

    # Fallback in-memory
    if not _in_memory_high_queue.empty():
        item = await _in_memory_high_queue.get()
        return item, 1
    if not _in_memory_low_queue.empty():
        item = await _in_memory_low_queue.get()
        return item, 2

    return None, 0


def start_analysis(db: Session, analysis_run_id: UUID) -> AnalysisRun:
    analysis = db.get(AnalysisRun, analysis_run_id)
    if analysis is None:
        raise ValueError("Không tìm thấy yêu cầu phân tích")

    if analysis.status != "PENDING":
        raise ValueError("Chỉ có thể bắt đầu yêu cầu đang PENDING")

    analysis.status = "PROCESSING"
    analysis.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)
    return analysis


def complete_analysis(
    db: Session,
    analysis_run_id: UUID,
    result_place_id: UUID | None = None,
    keyframes_data: Any = None,
    ocr_data: Any = None,
    execution_metrics: Any = None,
) -> AnalysisRun:
    analysis = db.get(AnalysisRun, analysis_run_id)
    if analysis is None:
        raise ValueError("Không tìm thấy yêu cầu phân tích")

    if analysis.status != "PROCESSING":
        raise ValueError("Yêu cầu phải ở trạng thái PROCESSING")

    analysis.status = "COMPLETED"
    analysis.result_place_id = result_place_id
    analysis.error_message = None
    if keyframes_data is not None:
        analysis.keyframes_data = keyframes_data
    if ocr_data is not None:
        analysis.ocr_data = ocr_data
    if execution_metrics is not None:
        analysis.execution_metrics = execution_metrics
    analysis.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(analysis)
    return analysis


def fail_analysis(
    db: Session,
    analysis_run_id: UUID,
    error_message: str,
) -> AnalysisRun:
    analysis = db.get(AnalysisRun, analysis_run_id)
    if analysis is None:
        raise ValueError("Không tìm thấy yêu cầu phân tích")

    if analysis.status not in ("PENDING", "PROCESSING"):
        raise ValueError("Không thể đánh dấu thất bại cho yêu cầu này")

    analysis.status = "FAILED"
    analysis.error_message = error_message
    analysis.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(analysis)
    return analysis


async def process_analysis_run(
    db: Session,
    analysis_run_id: UUID,
    http_client: httpx.AsyncClient | None = None,
) -> AnalysisRun:
    """
    Luồng 3: Thực thi phân tích 1 task:
    1. start_analysis -> notify WebSocket PROCESSING
    2. Gọi External AI Server qua POST AI_SERVER_EXTRACT_URL (timeout=180s)
    3. Cập nhật videos & geocode address qua ArcGIS
    4. complete_analysis -> notify WebSocket COMPLETED
    """
    analysis = db.get(AnalysisRun, analysis_run_id)
    if not analysis:
        raise ValueError(f"AnalysisRun {analysis_run_id} not found")

    # 1. Đổi status -> PROCESSING
    analysis = start_analysis(db, analysis_run_id)
    if analysis.trigger_source == "USER_SUBMIT" and analysis.user_id:
        await websocket_manager.broadcast_analysis_update(
            user_id=analysis.user_id,
            analysis_run_id=analysis.id,
            video_id=analysis.video_id,
            status="PROCESSING",
        )

    # 2. Gọi External AI Server
    should_close_client = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=float(settings.AI_REQUEST_TIMEOUT))
        should_close_client = True

    try:
        payload = {"url": analysis.submitted_url}
        ai_resp = await http_client.post(settings.AI_SERVER_EXTRACT_URL, json=payload)

        if ai_resp.status_code != 200:
            err_msg = f"AI Server returned HTTP {ai_resp.status_code}: {ai_resp.text[:200]}"
            fail_analysis(db, analysis.id, err_msg)
            if analysis.trigger_source == "USER_SUBMIT" and analysis.user_id:
                await websocket_manager.broadcast_analysis_update(
                    user_id=analysis.user_id,
                    analysis_run_id=analysis.id,
                    video_id=analysis.video_id,
                    status="FAILED",
                    error_message=err_msg,
                )
            return analysis

        resp_json = ai_resp.json()
        if resp_json.get("status") != "SUCCESS":
            err_msg = resp_json.get("message") or resp_json.get("error") or "AI extraction did not return SUCCESS"
            fail_analysis(db, analysis.id, err_msg)
            if analysis.trigger_source == "USER_SUBMIT" and analysis.user_id:
                await websocket_manager.broadcast_analysis_update(
                    user_id=analysis.user_id,
                    analysis_run_id=analysis.id,
                    video_id=analysis.video_id,
                    status="FAILED",
                    error_message=err_msg,
                )
            return analysis

        data = resp_json.get("data", {})

        # 3. Ánh xạ response vào Database
        video = db.get(Video, analysis.video_id) if analysis.video_id else None
        if video and "video" in data:
            v_info = data["video"]
            video.duration_seconds = v_info.get("duration_seconds")
            video.file_size_mb = v_info.get("file_size_mb")
            if "title" in v_info and not video.title:
                video.title = v_info.get("title")

        if video and "transcript" in data:
            t_info = data["transcript"]
            transcript_text = t_info.get("text")
            video.transcript = transcript_text
            video.transcript_text = transcript_text

        result_place = None
        restaurant_data = data.get("restaurant")
        if restaurant_data and restaurant_data.get("name"):
            rest_name = restaurant_data.get("name")
            rest_addr = restaurant_data.get("address") or ""
            confidence_status = restaurant_data.get("confidence_status", "MEDIUM")
            evidence_sources = restaurant_data.get("evidence_sources") or []

            # Geocode địa chỉ qua ArcGIS
            lat, lon, norm_addr = await ArcGISGeocoder.geocode_address(rest_addr, client=http_client)

            # Tìm kiếm place đã tồn tại (theo normalized_address hoặc name)
            existing_place = None
            if rest_addr:
                existing_place = db.scalar(
                    select(Place).where(Place.name == rest_name, Place.address == rest_addr)
                )

            if existing_place:
                result_place = existing_place
                if lat is not None and lon is not None and not result_place.location:
                    result_place.latitude = lat
                    result_place.longitude = lon
                    result_place.normalized_address = norm_addr
                    result_place.location = WKTElement(f"POINT({lon} {lat})", srid=4326)
            else:
                loc_wkt = WKTElement(f"POINT({lon} {lat})", srid=4326) if (lat is not None and lon is not None) else None
                result_place = Place(
                    name=rest_name,
                    address=rest_addr,
                    normalized_address=norm_addr,
                    location=loc_wkt,
                    latitude=lat,
                    longitude=lon,
                    category=restaurant_data.get("category"),
                )
                db.add(result_place)
                db.flush()

            # Tạo video_place_matches
            if video and result_place:
                match_existing = db.scalar(
                    select(VideoPlaceMatch).where(
                        VideoPlaceMatch.video_id == video.id,
                        VideoPlaceMatch.place_id == result_place.id,
                    )
                )
                if not match_existing:
                    match = VideoPlaceMatch(
                        video_id=video.id,
                        place_id=result_place.id,
                        confidence_status=confidence_status,
                        evidence_sources=evidence_sources,
                    )
                    db.add(match)

        # 4. complete_analysis
        analysis = complete_analysis(
            db=db,
            analysis_run_id=analysis.id,
            result_place_id=result_place.id if result_place else None,
            keyframes_data=data.get("keyframes"),
            ocr_data=data.get("frames_ocr_details"),
            execution_metrics=data.get("execution_metrics"),
        )

        # 5. Thông báo WebSocket COMPLETED
        if analysis.trigger_source == "USER_SUBMIT" and analysis.user_id:
            rest_dict = None
            if result_place:
                rest_dict = {
                    "id": str(result_place.id),
                    "name": result_place.name,
                    "address": result_place.normalized_address or result_place.address,
                    "latitude": result_place.latitude,
                    "longitude": result_place.longitude,
                }
            await websocket_manager.broadcast_analysis_update(
                user_id=analysis.user_id,
                analysis_run_id=analysis.id,
                video_id=analysis.video_id,
                status="COMPLETED",
                restaurant=rest_dict,
                error_message=None,
            )

        return analysis

    except Exception as exc:
        logger.exception(f"Unexpected error analyzing run {analysis_run_id}: {exc}")
        err_msg = str(exc)
        fail_analysis(db, analysis.id, err_msg)
        if analysis.trigger_source == "USER_SUBMIT" and analysis.user_id:
            await websocket_manager.broadcast_analysis_update(
                user_id=analysis.user_id,
                analysis_run_id=analysis.id,
                video_id=analysis.video_id,
                status="FAILED",
                error_message=err_msg,
            )
        return analysis

    finally:
        if should_close_client:
            await http_client.aclose()
