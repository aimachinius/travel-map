from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
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


@router.get(
    "/analysis/{analysis_run_id}",
    response_model=AnalysisStatusResponse,
    summary="Xem chi tiết trạng thái, keyframes, ocr và metrics của một lượt phân tích",
)
def get_analysis_status(
    analysis_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis_run = db.get(AnalysisRun, analysis_run_id)

    if analysis_run is None or analysis_run.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy yêu cầu phân tích",
        )

    return analysis_run


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Xem thông tin chi tiết một video",
)
def get_video_detail(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy video",
        )

    # Kiểm tra quyền truy cập (video do user gửi hoặc video trong hệ thống)
    has_access = db.scalar(
        select(AnalysisRun.id)
        .where(
            AnalysisRun.video_id == video_id,
            (AnalysisRun.user_id == current_user.id) | (AnalysisRun.trigger_source == "SYSTEM_DISCOVERY"),
        )
        .limit(1)
    )

    if has_access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy video",
        )

    return video
