"""
Module downloader: Dịch vụ tải video ngắn từ TikTok và YouTube Shorts bằng yt-dlp & ffmpeg.
"""

import os
import re
import time
import hashlib
from typing import Dict, Any, Optional, Tuple
import yt_dlp

from ...utils.logger import get_logger

logger = get_logger("VideoDownloader")


class VideoDownloader:
    """
    Dịch vụ tải video độc lập hỗ trợ cả TikTok và YouTube Shorts.
    """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        try:
            os.makedirs(self.output_dir, exist_ok=True)
        except FileExistsError:
            pass
        self.format_pref = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

    @staticmethod
    def extract_video_id(url: str) -> Tuple[str, str]:
        """
        Trích xuất Video ID và nền tảng (tiktok, youtube, unknown) từ URL.
        """
        clean_url = str(url).strip()
        
        # 1. YouTube Shorts hoặc YouTube thông thường
        yt_match = re.search(r"(?:shorts/|v=|youtu\.be/)([a-zA-Z0-9_-]{11})", clean_url)
        if yt_match:
            return yt_match.group(1), "youtube"

        # 2. TikTok
        tt_match = re.search(r"/video/(\d+)", clean_url)
        if tt_match:
            return tt_match.group(1), "tiktok"

        # TikTok rút gọn vt.tiktok.com
        if "tiktok.com" in clean_url:
            hash_id = hashlib.md5(clean_url.encode("utf-8")).hexdigest()[:16]
            return f"tt_{hash_id}", "tiktok"

        # Fallback hash
        hash_id = hashlib.md5(clean_url.encode("utf-8")).hexdigest()[:16]
        return f"vid_{hash_id}", "unknown"

    def download_video(
        self,
        url: str,
        video_id: Optional[str] = None,
        force_reload: bool = False
    ) -> Dict[str, Any]:
        """
        Tải video từ URL TikTok hoặc YouTube Shorts về thư mục lưu trữ cục bộ.
        """
        extracted_id, platform = self.extract_video_id(url)
        vid = str(video_id).strip() if video_id else extracted_id
        target_path = os.path.join(self.output_dir, f"{vid}.mp4")

        # 1. Kiểm tra cache nếu file đã tồn tại
        if not force_reload and os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
            size_mb = round(os.path.getsize(target_path) / (1024 * 1024), 2)
            logger.info(f"Video {vid} đã tồn tại trong cache ({size_mb} MB). Bỏ qua bước tải.")
            return {
                "video_id": vid,
                "platform": platform,
                "source_url": url,
                "status": "SKIPPED",
                "file_path": target_path,
                "file_size_mb": size_mb,
                "duration_seconds": 0.0,
                "error_message": "",
            }

        logger.info(f"Bắt đầu tải video từ URL ({platform}): {url}")
        outtmpl = os.path.join(self.output_dir, f"{vid}.%(ext)s")
        ydl_opts = {
            "format": self.format_pref,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "nooverwrites": not force_reload,
        }

        start_time = time.time()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Kiểm tra file đã xuất ra thực tế
            actual_file = None
            for ext in [".mp4", ".mkv", ".webm"]:
                cand = os.path.join(self.output_dir, f"{vid}{ext}")
                if os.path.exists(cand) and os.path.getsize(cand) > 1000:
                    actual_file = cand
                    break

            if actual_file:
                size_mb = round(os.path.getsize(actual_file) / (1024 * 1024), 2)
                elapsed = round(time.time() - start_time, 2)
                logger.info(f"Tải video thành công: {actual_file} ({size_mb} MB trong {elapsed}s)")
                return {
                    "video_id": vid,
                    "platform": platform,
                    "source_url": url,
                    "status": "SUCCESS",
                    "file_path": actual_file,
                    "file_size_mb": size_mb,
                    "duration_seconds": elapsed,
                    "error_message": "",
                }
            else:
                raise FileNotFoundError("Không tìm thấy file video sau khi yt-dlp hoàn tất.")

        except Exception as exc:
            err = str(exc)
            clean_err = (
                "Video ở chế độ riêng tư" if "Private video" in err
                else "Video bị xóa hoặc không khả dụng" if ("unavailable" in err or "404" in err)
                else "Bị chặn truy cập từ nền tảng / Rate limit" if ("10231" in err or "429" in err)
                else err[:200]
            )
            elapsed = round(time.time() - start_time, 2)
            logger.error(f"Lỗi khi tải video {vid}: {clean_err}")
            return {
                "video_id": vid,
                "platform": platform,
                "source_url": url,
                "status": "FAILED",
                "file_path": "",
                "file_size_mb": 0.0,
                "duration_seconds": elapsed,
                "error_message": clean_err,
            }
