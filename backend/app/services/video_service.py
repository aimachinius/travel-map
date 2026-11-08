import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.video import Video
from app.models.video_place_match import VideoPlaceMatch
from app.schemas.video import VideoSubmitRequest


def extract_video_info(video_url: str) -> tuple[str, str]:
    if "tiktok.com" in video_url:
        platform = "tiktok"
        patterns = [
            r"/video/(\d+)",
            r"v/(\d+)",
        ]

    elif "youtube.com" in video_url or "youtu.be" in video_url:
        platform = "youtube"
        patterns = [
            r"[?&]v=([a-zA-Z0-9_-]{11})",
            r"youtu\.be/([a-zA-Z0-9_-]{11})",
            r"/shorts/([a-zA-Z0-9_-]{11})",
            r"/embed/([a-zA-Z0-9_-]{11})",
        ]

    else:
        raise ValueError("Nền tảng video chưa được hỗ trợ. Chỉ hỗ trợ TikTok và YouTube")

    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            return platform, match.group(1)

    raise ValueError("Không thể xác định ID video từ URL")


async def submit_video(
    db: Session,
    data: VideoSubmitRequest,
    user_id: UUID,
    force_reanalyze: bool = False,
) -> tuple[Video, AnalysisRun, bool]:
    """
    Luồng 1: Người dùng gửi link video phân tích.
    Trả về (video, analysis_run, is_cached_completed).
    """
    video_url = str(data.video_url).strip()
    platform, platform_video_id = extract_video_info(video_url)

    # 1. Get or Create Video
    video = db.scalar(
        select(Video).where(
            Video.platform == platform,
            Video.platform_video_id == platform_video_id,
        )
    )

    if video is None:
        video = Video(
            platform=platform,
            platform_video_id=platform_video_id,
            video_url=video_url,
        )
        db.add(video)
        db.flush()

    # 2. Kiểm tra nếu đã có kết quả phân tích COMPLETED trước đó
    if not force_reanalyze:
        completed_run = db.scalar(
            select(AnalysisRun).where(
                AnalysisRun.video_id == video.id,
                AnalysisRun.status == "COMPLETED",
            ).order_by(AnalysisRun.created_at.desc()).limit(1)
        )
        if completed_run is not None:
            return video, completed_run, True

    # 3. Tạo analysis_runs mới với priority = 1, trigger_source = USER_SUBMIT
    analysis_run = AnalysisRun(
        user_id=user_id,
        video_id=video.id,
        submitted_url=video_url,
        status="PENDING",
        trigger_source="USER_SUBMIT",
        priority=1,
    )

    db.add(analysis_run)
    try:
        db.commit()
        db.refresh(video)
        db.refresh(analysis_run)
    except Exception:
        db.rollback()
        raise

    # 4. Đẩy task vào hàng đợi ưu tiên cao
    from app.services.analysis_service import enqueue_analysis
    await enqueue_analysis(analysis_run.id, priority=1)

    return video, analysis_run, False
