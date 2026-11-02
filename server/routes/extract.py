"""
Module extract: Xử lý các endpoint trích xuất thông tin quán ăn đồng bộ (/api/v1/extract) và bất đồng bộ (/api/v1/jobs).
"""

import asyncio
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

from ..schemas.request import UrlExtractRequest, JobCreateRequest
from ..schemas.response import ExtractionResponse, JobCreateResponse, JobStatusResponse
from ..dependencies import get_pipeline, get_job_manager, get_gpu_semaphore, get_server_config
from ..services.job_manager import JobStatus
from ...utils.logger import get_logger

logger = get_logger("ExtractRouter")
router = APIRouter(prefix="/api/v1", tags=["Extraction"])


def is_supported_url(url: str) -> bool:
    """Kiểm tra xem URL có thuộc TikTok hoặc YouTube Shorts hay không."""
    u = str(url).lower().strip()
    return any(p in u for p in ["tiktok.com", "youtube.com", "youtu.be"])


async def execute_background_job(
    job_id: str,
    req: JobCreateRequest,
    pipeline,
    job_manager,
    gpu_semaphore,
):
    """Worker thực thi job ngầm trong thread pool dưới sự kiểm soát của GPU Semaphore."""
    job_manager.update_job(job_id, status=JobStatus.QUEUED, stage="Đang xếp hàng chờ GPU", progress_pct=5)

    async with gpu_semaphore:
        try:
            def update_progress(stage_name: str, pct: int):
                job_manager.update_job(job_id, status=JobStatus.TRANSCRIBING if pct < 70 else JobStatus.VLM_INFERENCE, stage=stage_name, progress_pct=pct)

            # Thực thi pipeline trong worker thread
            result = await asyncio.to_thread(
                pipeline.process_url,
                url=req.url,
                top_k=req.top_k_frames,
                force_reload=req.force_reload,
                keep_raw_video=req.keep_raw_video,
                status_callback=update_progress,
            )

            if result.get("success", False):
                job_manager.update_job(
                    job_id,
                    status=JobStatus.COMPLETED,
                    stage="Hoàn thành xuất sắc",
                    progress_pct=100,
                    result=result.get("data"),
                )
            else:
                job_manager.update_job(
                    job_id,
                    status=JobStatus.FAILED,
                    stage="Thất bại trong pipeline",
                    progress_pct=100,
                    error_message=result.get("error_message", "Lỗi xử lý không xác định."),
                )
        except Exception as e:
            logger.error(f"Lỗi khi thực thi background job {job_id}: {e}")
            job_manager.update_job(
                job_id,
                status=JobStatus.FAILED,
                stage="Lỗi hệ thống",
                progress_pct=100,
                error_message=str(e),
            )


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Trích xuất trực tiếp thông tin quán ăn từ URL (Synchronous)",
    description="Nhận URL TikTok hoặc YouTube Shorts, chờ xử lý và trả về kết quả JSON ngay lập tức."
)
async def extract_restaurant_sync(
    req: UrlExtractRequest,
    pipeline = Depends(get_pipeline),
    gpu_semaphore: asyncio.Semaphore = Depends(get_gpu_semaphore),
    config = Depends(get_server_config),
):
    # 1. Kiểm thực tính hợp lệ của URL
    if not req.url or not req.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trường 'url' không được để trống."
        )

    if not is_supported_url(req.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nền tảng không được hỗ trợ. Hệ thống hiện chỉ hỗ trợ video từ TikTok và YouTube Shorts."
        )

    # 2. Cơ chế Fast-Fail chống nghẽn Timeout Reverse Proxy
    if gpu_semaphore.locked():
        logger.info("GPU đang bận xử lý tác vụ khác. Client đang xếp hàng chờ...")

    # 3. Điều phối qua GPU Semaphore và chuyển sang Worker Thread
    async with gpu_semaphore:
        try:
            logger.info(f"Bắt đầu xử lý đồng bộ URL: {req.url}")
            result = await asyncio.to_thread(
                pipeline.process_url,
                url=req.url,
                top_k=req.top_k_frames,
                force_reload=req.force_reload,
                keep_raw_video=req.keep_raw_video,
            )

            if not result.get("success", False):
                if result.get("status") == "DOWNLOAD_FAILED":
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=result.get("error_message", "Không thể tải video từ URL.")
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=result.get("error_message", "Lỗi xử lý nội bộ trong pipeline.")
                    )

            return result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Ngoại lệ chưa bắt trong /api/v1/extract: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi máy chủ nội bộ: {str(e)}"
            )


@router.post(
    "/jobs",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Tạo tiến trình bóc tách video bất đồng bộ (Asynchronous Queue)",
    description="Nhận URL video và đưa vào hàng đợi ngầm. Trả về job_id để client thăm dò định kỳ, tránh timeout."
)
async def create_extraction_job(
    req: JobCreateRequest,
    background_tasks: BackgroundTasks,
    pipeline = Depends(get_pipeline),
    job_manager = Depends(get_job_manager),
    gpu_semaphore: asyncio.Semaphore = Depends(get_gpu_semaphore),
):
    if not req.url or not req.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trường 'url' không được để trống."
        )

    if not is_supported_url(req.url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ hỗ trợ video từ TikTok và YouTube Shorts."
        )

    job_id = job_manager.create_job(req.url, metadata=req.model_dump() if hasattr(req, "model_dump") else req.dict())

    # Khởi chạy tác vụ nền
    background_tasks.add_task(
        execute_background_job,
        job_id=job_id,
        req=req,
        pipeline=pipeline,
        job_manager=job_manager,
        gpu_semaphore=gpu_semaphore,
    )

    now_iso = asyncio.get_event_loop().time()
    return {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "created_at": str(now_iso),
        "message": "Yêu cầu đã được tiếp nhận và đang xếp hàng xử lý ngầm.",
    }


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Kiểm tra trạng thái và nhận kết quả của Job",
    description="Thăm dò (polling) trạng thái tiến độ (progress_pct) và nhận kết quả khi trạng thái chuyển sang COMPLETED."
)
async def get_job_status(job_id: str, job_manager = Depends(get_job_manager)):
    job_info = job_manager.get_job(job_id)
    if not job_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy công việc với ID: '{job_id}'."
        )
    return job_info


@router.get(
    "/jobs",
    summary="Danh sách các công việc bóc tách gần đây",
)
async def list_recent_jobs(limit: int = 20, job_manager = Depends(get_job_manager)):
    return job_manager.list_jobs(limit=limit)
