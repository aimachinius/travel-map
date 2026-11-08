import asyncio
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import SessionLocal, get_db
from app.models.analysis_run import AnalysisRun
from app.models.user import User
from app.models.video import Video
from app.schemas.video import (
    AnalysisStatusResponse,
    VideoResponse,
    VideoSubmitRequest,
    VideoSubmitResponse,
)
from app.services.video_service import submit_video

router = APIRouter(
    prefix="/videos",
    tags=["Videos"],
)

# In-memory TTL cache (60s) cho các AnalysisRun đã COMPLETED và Video chi tiết (phục vụ đọc tần suất cao TC_PERF_09)
_COMPLETED_ANALYSIS_CACHE: dict[UUID, tuple[AnalysisRun, float]] = {}
_VIDEO_DETAIL_CACHE: dict[tuple[UUID, UUID], tuple[Video, float]] = {}
_VIDEO_CACHE_TTL_SEC = 60.0


@router.post(
    "/submit",
    response_model=VideoSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Gửi link video TikTok hoặc YouTube để phân tích quán ăn",
)
async def submit_video_endpoint(
    data: VideoSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        video, analysis_run, is_cached = await submit_video(
            db=db,
            data=data,
            user_id=current_user.id,
            force_reanalyze=data.force_reanalyze,
        )

        return VideoSubmitResponse(
            analysis_run_id=analysis_run.id,
            video_id=video.id,
            submitted_url=analysis_run.submitted_url,
            status=analysis_run.status,
            cached=is_cached,
            created_at=analysis_run.created_at,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[VideoResponse],
    summary="Danh sách video do người dùng hiện tại đã gửi",
)
def get_my_videos(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    videos = db.scalars(
        select(Video)
        .join(AnalysisRun, AnalysisRun.video_id == Video.id)
        .where(AnalysisRun.user_id == current_user.id)
        .distinct()
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return list(videos)


@router.get(
    "/analysis",
    response_model=list[AnalysisStatusResponse],
    summary="Lịch sử các lần yêu cầu phân tích video của người dùng",
)
def get_analysis_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analyses = db.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.user_id == current_user.id)
        .order_by(AnalysisRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return list(analyses)


def _fetch_analysis_status_sync(analysis_run_id: UUID, user_id: UUID) -> AnalysisRun | None:
    with SessionLocal() as db:
        analysis_run = db.get(AnalysisRun, analysis_run_id)
        if analysis_run is None or analysis_run.user_id != user_id:
            return None
        _ = (
            analysis_run.id,
            analysis_run.user_id,
            analysis_run.video_id,
            analysis_run.submitted_url,
            analysis_run.status,
            analysis_run.trigger_source,
            analysis_run.priority,
            analysis_run.result_place_id,
            analysis_run.keyframes_data,
            analysis_run.ocr_data,
            analysis_run.execution_metrics,
            analysis_run.error_message,
            analysis_run.started_at,
            analysis_run.completed_at,
            analysis_run.created_at,
            analysis_run.updated_at,
        )
        try:
            db.expunge(analysis_run)
        except Exception:
            pass
        return analysis_run


@router.get(
    "/analysis/{analysis_run_id}",
    response_model=AnalysisStatusResponse,
    summary="Xem chi tiết trạng thái, keyframes, ocr và metrics của một lượt phân tích",
)
async def get_analysis_status(
    analysis_run_id: UUID,
    current_user: User = Depends(get_current_user),
):
    now = time.monotonic()
    cached = _COMPLETED_ANALYSIS_CACHE.get(analysis_run_id)
    if cached is not None and now < cached[1]:
        run_obj = cached[0]
        if run_obj.user_id == current_user.id:
            return run_obj

    analysis_run = await asyncio.to_thread(_fetch_analysis_status_sync, analysis_run_id, current_user.id)

    if analysis_run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy yêu cầu phân tích",
        )

    if analysis_run.status == "COMPLETED":
        if len(_COMPLETED_ANALYSIS_CACHE) > 2000:
            _COMPLETED_ANALYSIS_CACHE.clear()
        _COMPLETED_ANALYSIS_CACHE[analysis_run_id] = (analysis_run, now + _VIDEO_CACHE_TTL_SEC)

    return analysis_run


def _fetch_video_detail_sync(video_id: UUID, user_id: UUID) -> Video | None:
    with SessionLocal() as db:
        video = db.get(Video, video_id)
        if video is None:
            return None

        has_access = db.scalar(
            select(AnalysisRun.id)
            .where(
                AnalysisRun.video_id == video_id,
                (AnalysisRun.user_id == user_id) | (AnalysisRun.trigger_source == "SYSTEM_DISCOVERY"),
            )
            .limit(1)
        )
        if has_access is None:
            return None

        _ = (
            video.id,
            video.platform,
            video.platform_video_id,
            video.video_url,
            video.title,
            video.caption,
            video.duration_seconds,
            video.file_size_mb,
            video.thumbnail_url,
            video.author_name,
            video.transcript,
            video.transcript_text,
            video.created_at,
            video.updated_at,
        )
        try:
            db.expunge(video)
        except Exception:
            pass
        return video


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Xem thông tin chi tiết một video",
)
async def get_video_detail(
    video_id: UUID,
    current_user: User = Depends(get_current_user),
):
    now = time.monotonic()
    cache_key = (video_id, current_user.id)
    cached = _VIDEO_DETAIL_CACHE.get(cache_key)
    if cached is not None and now < cached[1]:
        return cached[0]

    video = await asyncio.to_thread(_fetch_video_detail_sync, video_id, current_user.id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy video",
        )

    if len(_VIDEO_DETAIL_CACHE) > 2000:
        _VIDEO_DETAIL_CACHE.clear()
    _VIDEO_DETAIL_CACHE[cache_key] = (video, now + _VIDEO_CACHE_TTL_SEC)

    return video
