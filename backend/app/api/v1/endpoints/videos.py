
from app.models.video import Video
from sqlalchemy import select
from uuid import UUID

from app.models.analysis_run import AnalysisRun
from app.schemas.video import (
    VideoSubmitRequest,
    VideoSubmitResponse,
    VideoResponse,
    AnalysisStatusResponse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.video import (
    VideoSubmitRequest,
    VideoSubmitResponse,
    VideoResponse,
)
from app.services.video_service import submit_video


router = APIRouter(
    prefix="/videos",
    tags=["Videos"],
)


@router.post(
    "/submit",
    response_model=VideoSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_video(
    data: VideoSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        video, analysis_run = submit_video(
            db=db,
            data=data,
            user_id=current_user.id,
        )

        return {
            "analysis_run_id": analysis_run.id,
            "submitted_url": analysis_run.submitted_url,
            "status": analysis_run.status,
            "video": VideoResponse.model_validate(video),
            "created_at": analysis_run.created_at,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

@router.get(
    "/analysis/{analysis_run_id}",
    response_model=AnalysisStatusResponse,
)
def get_analysis_status(
    analysis_run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis_run = db.get(AnalysisRun, analysis_run_id)

    if (
        analysis_run is None
        or analysis_run.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy yêu cầu phân tích",
        )

    return analysis_run

@router.get(
    "/analysis",
    response_model=list[AnalysisStatusResponse],
)
def get_analysis_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analyses = db.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.user_id == current_user.id)
        .order_by(AnalysisRun.created_at.desc())
    ).all()

    return analyses
@router.get(
    "",
    response_model=list[VideoResponse],
)
def get_my_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    videos = db.scalars(
        select(Video)
        .join(
            AnalysisRun,
            AnalysisRun.video_id == Video.id,
        )
        .where(AnalysisRun.user_id == current_user.id)
        .distinct()
        .order_by(Video.created_at.desc())
    ).all()

    return videos
@router.get(
    "/{video_id}",
    response_model=VideoResponse,
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

    has_access = db.scalar(
        select(AnalysisRun.id).where(
            AnalysisRun.video_id == video_id,
            AnalysisRun.user_id == current_user.id,
        ).limit(1)
    )

    if has_access is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy video",
        )

    return video

