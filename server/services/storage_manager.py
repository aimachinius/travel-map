"""
Module storage_manager: Quản lý bộ nhớ đệm kết quả JSON, thời hạn sống của file (TTL 24h) và hạn mức dung lượng đĩa cứng.
"""

import os
import time
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
import numpy as np

from ...utils.logger import get_logger

logger = get_logger("StorageManager")


class StorageManager:
    """
    Quản lý lưu trữ tệp tin và dọn dẹp định kỳ cho máy chủ AI.
    """
    def __init__(self, storage_dir: str):
        self.storage_dir = os.path.abspath(storage_dir)
        self.videos_dir = os.path.join(self.storage_dir, "videos")
        self.keyframes_dir = os.path.join(self.storage_dir, "keyframes")
        self.cache_dir = os.path.join(self.storage_dir, "cache")

        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.keyframes_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

    @staticmethod
    def hash_url(url: str) -> str:
        """Tạo mã MD5 duy nhất đại diện cho URL."""
        return hashlib.md5(str(url).strip().encode("utf-8")).hexdigest()

    def get_cached_result(self, url: str) -> Optional[Dict[str, Any]]:
        """Lấy kết quả đã suy luận trước đó từ cache nếu có."""
        cache_file = os.path.join(self.cache_dir, f"{self.hash_url(url)}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info(f"Đã tìm thấy kết quả trong cache cho URL: {url}")
                return data
            except Exception as e:
                logger.warning(f"Lỗi khi đọc file cache {cache_file}: {e}")
        return None

    def save_cache_result(self, url: str, result_data: Dict[str, Any]):
        """Lưu kết quả bóc tách vào cache JSON."""
        cache_file = os.path.join(self.cache_dir, f"{self.hash_url(url)}.json")
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Đã lưu cache JSON tại: {cache_file}")
        except Exception as e:
            logger.warning(f"Lỗi khi lưu cache JSON {cache_file}: {e}")

    def safe_remove_file(self, file_path: str) -> bool:
        """Xóa file an toàn mà không làm sập tiến trình nếu file đang bị khóa hoặc không tồn tại."""
        if not file_path or not os.path.exists(file_path):
            return False
        try:
            os.remove(file_path)
            logger.info(f"Đã xóa an toàn file: {file_path}")
            return True
        except Exception as e:
            logger.warning(f"Không thể xóa file {file_path}: {e}")
            return False

    def get_total_storage_size_mb(self) -> float:
        """Tính tổng dung lượng (MB) của thư mục lưu trữ."""
        total_bytes = 0
        for root, _, files in os.walk(self.storage_dir):
            for file in files:
                p = os.path.join(root, file)
                try:
                    total_bytes += os.path.getsize(p)
                except Exception:
                    pass
        return round(total_bytes / (1024 * 1024), 2)

    def clean_expired_files(self, ttl_hours: int = 24, max_storage_mb: int = 5000) -> Dict[str, Any]:
        """
        Tiến trình dọn rác định kỳ:
        1. Xóa các file có tuổi thọ vượt quá TTL (mặc định 24h).
        2. Nếu dung lượng lưu trữ vẫn vượt quá `max_storage_mb`, xóa theo thứ tự cũ nhất (LRU).
        """
        now = time.time()
        ttl_seconds = ttl_hours * 3600
        deleted_count = 0
        freed_bytes = 0

        all_files: List[Tuple[str, float, int]] = []  # (path, mtime, size)

        # 1. Quét toàn bộ file trong các thư mục lưu trữ
        for target_folder in [self.videos_dir, self.keyframes_dir, self.cache_dir]:
            if not os.path.exists(target_folder):
                continue
            for root, _, files in os.walk(target_folder):
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        stat = os.stat(file_path)
                        age = now - stat.st_mtime
                        if age > ttl_seconds:
                            size = stat.st_size
                            os.remove(file_path)
                            deleted_count += 1
                            freed_bytes += size
                        else:
                            all_files.append((file_path, stat.st_mtime, stat.st_size))
                    except Exception as e:
                        logger.debug(f"Bỏ qua file khi dọn rác: {file_path} ({e})")

        # 2. Kiểm tra hạn mức dung lượng đĩa (Quota limit)
        current_mb = self.get_total_storage_size_mb()
        if current_mb > max_storage_mb:
            logger.warning(f"Dung lượng lưu trữ ({current_mb} MB) vượt ngưỡng {max_storage_mb} MB. Kích hoạt dọn rác LRU...")
            # Sắp xếp file theo thời gian sửa đổi cũ nhất lên đầu
            all_files.sort(key=lambda x: x[1])
            for file_path, _, size in all_files:
                if current_mb <= max_storage_mb * 0.8:  # Dọn về mức 80% hạn mức
                    break
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    freed_bytes += size
                    current_mb -= size / (1024 * 1024)
                except Exception:
                    pass

        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        if deleted_count > 0:
            logger.info(f"Đã dọn dẹp {deleted_count} file cũ, giải phóng {freed_mb} MB dung lượng.")

        return {
            "deleted_count": deleted_count,
            "freed_mb": freed_mb,
            "current_total_mb": current_mb,
        }

    def save_clean_keyframes(
        self,
        video_id: str,
        frames: List[Any],
    ) -> List[str]:
        """
        Lưu các khung hình sạch (clean keyframes) ra ổ đĩa và trả về danh sách đường dẫn URL phục vụ client.
        Định dạng lưu: storage/keyframes/{video_id}/frame_{idx:02d}.jpg
        URL trả về: /api/v1/keyframes/{video_id}/frame_{idx:02d}.jpg
        """
        video_kf_dir = os.path.join(self.keyframes_dir, str(video_id))
        os.makedirs(video_kf_dir, exist_ok=True)
        url_paths: List[str] = []

        for idx, frame in enumerate(frames):
            frame_filename = f"frame_{idx:02d}.jpg"
            file_path = os.path.join(video_kf_dir, frame_filename)
            try:
                if hasattr(frame, "save"):
                    # PIL Image
                    frame.save(file_path, "JPEG", quality=95)
                elif isinstance(frame, np.ndarray):
                    # BGR numpy array
                    from ...utils.io_utils import cv2_imwrite
                    cv2_imwrite(file_path, frame)
                else:
                    logger.warning(f"Frame kiểu {type(frame)} không được hỗ trợ lưu.")
                    continue
                url_paths.append(f"/api/v1/keyframes/{video_id}/{frame_filename}")
            except Exception as e:
                logger.error(f"Lỗi khi lưu keyframe {idx} cho video {video_id}: {e}")

        logger.info(f"Đã lưu {len(url_paths)} clean keyframes cho video {video_id} tại {video_kf_dir}")
        return url_paths
