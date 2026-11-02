"""
Module app: Khởi tạo ứng dụng FastAPI chính, cấu hình CORS, tích hợp Lifespan quản lý mô hình AI,
kích hoạt tiến trình dọn dẹp TTL và khởi động Cầu nối mạng Cloudflare Tunnel.
"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .dependencies import (
    get_server_config,
    get_pipeline,
    get_tunnel_manager,
    set_server_config,
)
from .routes.extract import router as extract_router
from .routes.health import router as health_router
from .routes.static_files import router as static_router
from ..utils.logger import get_logger

logger = get_logger("FastAPIServer")

# Biến cờ kiểm soát tiến trình dọn rác nền
_cleaner_task = None


async def periodic_storage_cleaner(pipeline, config, interval_seconds: int = 3600):
    """Tiến trình chạy ngầm định kỳ dọn rác các file quá 24h hoặc khi ổ đĩa vượt quá hạn mức."""
    logger.info(f"Đã kích hoạt tiến trình dọn rác định kỳ (chu kỳ {interval_seconds}s).")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("Đang thực hiện kiểm tra và dọn dẹp file cũ trong storage...")
            pipeline.storage_manager.clean_expired_files(
                ttl_hours=config.ttl_hours,
                max_storage_mb=config.max_storage_mb
            )
        except asyncio.CancelledError:
            logger.info("Tiến trình dọn rác định kỳ đã dừng.")
            break
        except Exception as e:
            logger.error(f"Lỗi trong tiến trình dọn rác định kỳ: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Quản lý vòng đời khởi động và kết thúc của FastAPI Server."""
    global _cleaner_task
    config = get_server_config()
    logger.info("=" * 60)
    logger.info("🚀 [KHỞI ĐỘNG RESTAURANT EXTRACTION AI SERVER V3.0 (PURE VISION)]")
    logger.info(f"📍 Cổng nội bộ: http://{config.host}:{config.port}")
    logger.info(f"⚙️ Chế độ Low-VRAM: {config.low_vram_mode}")
    logger.info(f"⚡ Bộ phát hiện văn bản: GPUDBNetDetector ({config.dbnet_onnx_path})")
    logger.info(f"👁️ Mô hình VLM: {config.vlm_model_id}")
    logger.info("=" * 60)

    # 1. Khởi tạo pipeline
    pipeline = get_pipeline()

    # 2. Khởi chạy tiến trình dọn rác định kỳ
    _cleaner_task = asyncio.create_task(
        periodic_storage_cleaner(pipeline, config, interval_seconds=3600)
    )

    # 3. Khởi động Cầu nối mạng (Tunnel)
    tunnel_mgr = get_tunnel_manager()
    if config.tunnel_provider != "none":
        tunnel_url = tunnel_mgr.start_tunnel()
        if tunnel_url:
            logger.info(f"🌐 Public API Endpoint: {tunnel_url}/api/v1/extract")

    yield

    # Kết thúc
    logger.info("Đang dừng AI Server...")
    if _cleaner_task and not _cleaner_task.done():
        _cleaner_task.cancel()
    tunnel_mgr.stop_tunnel()
    logger.info("AI Server đã dừng an toàn.")


def create_app() -> FastAPI:
    """Tạo instance FastAPI với cấu hình đầy đủ."""
    app = FastAPI(
        title="Restaurant Extraction AI Server v3.0",
        description=(
            "AI Server độc lập trích xuất thông tin quán ăn (tên quán, địa chỉ) từ URL video TikTok & YouTube Shorts. "
            "Kiến trúc Pure Vision tăng tốc GPU (FastSinglePassSampler + GPUDBNet + Vintern-1B Majority Voting)."
        ),
        version="3.0.0",
        lifespan=lifespan,
    )

    # Cho phép tất cả các domain client gọi vào (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Đăng ký các router
    app.include_router(health_router)
    app.include_router(extract_router)
    app.include_router(static_router)

    return app


app = create_app()
