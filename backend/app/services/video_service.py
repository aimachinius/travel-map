
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.video import Video
from app.models.analysis_run import AnalysisRun
from app.schemas.video import VideoSubmitRequest


def extract_video_info(video_url: str) -> tuple[str, str]:
    if "tiktok.com" in video_url:
        platform = "tiktok"
        patterns = [
            r"/video/(\d+)",
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
        raise ValueError("Nền tảng video chưa được hỗ trợ")

    for pattern in patterns:
        match = re.search(pattern, video_url)
        if match:
            return platform, match.group(1)

    raise ValueError("Không thể xác định ID video từ URL")


def submit_video(
    db: Session,
    data: VideoSubmitRequest,
    user_id,
) -> tuple[Video, AnalysisRun]:

    video_url = str(data.video_url)
    platform, platform_video_id = extract_video_info(video_url)

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

    analysis_run = AnalysisRun(
        user_id=user_id,
        video_id=video.id,
        submitted_url=video_url,
        status="PENDING",
    )

    db.add(analysis_run)

    try:
        db.commit()
        db.refresh(video)
        db.refresh(analysis_run)
    except Exception:
        db.rollback()
        raise

    return video, analysis_run
