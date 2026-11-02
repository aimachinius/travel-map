"""
Module health: Endpoint kiểm tra sức khỏe hệ thống, tài nguyên GPU VRAM và bộ URL kết nối song hành.
"""

from fastapi import APIRouter, Depends
import torch

from ..schemas.response import HealthResponse, AccessUrls
from ..dependencies import get_tunnel_manager, get_pipeline, get_server_config

router = APIRouter(tags=["System Health"])


@router.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Kiểm tra trạng thái máy chủ, VRAM và Cầu nối mạng",
    description="Trả về thông tin kết nối cổng local (8000), Public Tunnel URL, tình trạng GPU và các mô hình đã nạp."
)
@router.get(
    "/health",
    response_model=HealthResponse,
    include_in_schema=False,
)
async def check_health(
    tunnel_manager = Depends(get_tunnel_manager),
    pipeline = Depends(get_pipeline),
    config = Depends(get_server_config),
):
    cuda_available = torch.cuda.is_available()
    gpu_name = None
    vram_used = None
    vram_total = None

    if cuda_available:
        try:
            gpu_name = torch.cuda.get_device_name(0)
            vram_used = int(torch.cuda.memory_allocated(0) / (1024 * 1024))
            vram_total = int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024))
        except Exception:
            pass

    urls_info = tunnel_manager.get_access_urls()
    access_urls = AccessUrls(
        local_url=urls_info["local_url"],
        public_tunnel_url=urls_info["public_tunnel_url"],
        tunnel_provider=urls_info["tunnel_provider"],
        is_tunnel_active=urls_info["is_tunnel_active"],
    )

    active_provider = getattr(pipeline.frame_selector.text_detector, "active_provider", "CPUExecutionProvider")
    models_state = {
        "dbnet_onnx": pipeline.frame_selector.text_detector is not None,
        "vintern_1b": pipeline.vlm_extractor is not None,
    }

    return HealthResponse(
        status="HEALTHY",
        access_urls=access_urls,
        gpu_available=cuda_available,
        gpu_name=gpu_name,
        onnx_provider=active_provider,
        vram_used_mb=vram_used,
        vram_total_mb=vram_total,
        models_loaded=models_state,
    )
