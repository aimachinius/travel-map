"""
Module job_manager: Quản lý hàng đợi công việc bóc tách video bất đồng bộ trong RAM (Thread-Safe).
"""

import time
import uuid
import threading
from typing import Dict, Any, Optional, List

from ...utils.logger import get_logger

logger = get_logger("JobManager")


class JobStatus:
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    TRANSCRIBING = "TRANSCRIBING"
    SELECTING_FRAMES = "SELECTING_FRAMES"
    VLM_INFERENCE = "VLM_INFERENCE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobManager:
    """
    Quản lý danh sách tác vụ ngầm cho các client di động/web không muốn bị timeout HTTP.
    """
    def __init__(self, max_history: int = 1000):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.max_history = max_history
        self._lock = threading.Lock()

    def create_job(self, url: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Tạo một job mới với ID ngẫu nhiên và đưa vào trạng thái QUEUED."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        job_info = {
            "job_id": job_id,
            "url": str(url).strip(),
            "status": JobStatus.QUEUED,
            "stage": "Đang chờ điều phối",
            "progress_pct": 0,
            "created_at": now_iso,
            "updated_at": now_iso,
            "metadata": metadata or {},
            "result": None,
            "error_message": None,
        }

        with self._lock:
            # Dọn bớt job cũ nếu vượt quá dung lượng lịch sử
            if len(self.jobs) >= self.max_history:
                oldest_key = next(iter(self.jobs))
                del self.jobs[oldest_key]
            self.jobs[job_id] = job_info

        logger.info(f"Đã tạo Job mới: {job_id} cho URL: {url}")
        return job_id

    def update_job(
        self,
        job_id: str,
        status: str,
        stage: Optional[str] = None,
        progress_pct: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ):
        """Cập nhật tiến độ và trạng thái của Job."""
        with self._lock:
            if job_id not in self.jobs:
                return

            j = self.jobs[job_id]
            j["status"] = status
            j["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if stage is not None:
                j["stage"] = stage
            if progress_pct is not None:
                j["progress_pct"] = max(0, min(100, progress_pct))
            if result is not None:
                j["result"] = result
            if error_message is not None:
                j["error_message"] = str(error_message)

        logger.debug(f"Job {job_id} -> {status} ({progress_pct}%): {stage}")

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết của một Job."""
        with self._lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Danh sách các job gần nhất."""
        with self._lock:
            items = list(self.jobs.values())[-limit:]
            return [dict(i) for i in reversed(items)]
