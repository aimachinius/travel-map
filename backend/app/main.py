import asyncio
from contextlib import asynccontextmanager
import logging
import sys

# Configure root logger so INFO logs from services and routers are visible in Docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logging.getLogger("app").setLevel(logging.INFO)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uuid import UUID

from app.api.v1.router import api_router
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


async def background_queue_worker():
    """
    Worker nền điều phối hàng đợi kép (Luồng 3):
    Liên tục rút task từ queue:high_priority trước, sau đó tới queue:low_priority.
    """
    from app.services.analysis_service import dequeue_next_analysis, process_analysis_run

    logger.info("Khởi động background queue worker cho Food Spot...")
    while True:
        try:
            run_id_str, priority = await dequeue_next_analysis()
            if run_id_str:
                logger.info(f"Worker rút được task {run_id_str} (priority {priority})")
                db = SessionLocal()
                try:
                    await process_analysis_run(db, UUID(run_id_str))
                except Exception as ex:
                    logger.exception(f"Lỗi khi worker xử lý task {run_id_str}: {ex}")
                finally:
                    db.close()
            else:
                # Không có task trong cả 2 hàng đợi, nghỉ một chút
                await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            logger.info("Background queue worker đã dừng.")
            break
        except Exception as e:
            logger.warning(f"Lỗi trong vòng lặp worker: {e}")
            await asyncio.sleep(3.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi chạy worker chạy nền
    worker_task = asyncio.create_task(background_queue_worker())
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Food Spot API",
    description="Backend API for the Food Spot application according to System Specification",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "Food Spot Backend",
        "version": "1.0.0",
    }


app.include_router(api_router, prefix="/api/v1")
