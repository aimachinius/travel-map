"""
Module test_downloader: Kiểm thử độc lập Module 1 - VideoDownloader (yt-dlp).
"""

import os
import unittest
import shutil

from src.server.services.downloader import VideoDownloader


class TestVideoDownloader(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "fixtures", "test_downloads")
        try:
            os.makedirs(self.test_dir, exist_ok=True)
        except FileExistsError:
            pass
        self.downloader = VideoDownloader(output_dir=self.test_dir)

    def tearDown(self):
        # Dọn dẹp các tệp tạm sau test mà không xóa cả thư mục để tránh lock trên Windows
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                fp = os.path.join(self.test_dir, f)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                except Exception:
                    pass

    def test_extract_video_id(self):
        # 1. YouTube Shorts chuẩn
        yt_url = "https://www.youtube.com/shorts/kJQP7kiw5Fk"
        vid, platform = self.downloader.extract_video_id(yt_url)
        self.assertEqual(vid, "kJQP7kiw5Fk")
        self.assertEqual(platform, "youtube")

        # 2. TikTok chuẩn
        tt_url = "https://www.tiktok.com/@user/video/7382910293819201823"
        vid2, platform2 = self.downloader.extract_video_id(tt_url)
        self.assertEqual(vid2, "7382910293819201823")
        self.assertEqual(platform2, "tiktok")

        # 3. TikTok rút gọn
        tt_short = "https://vt.tiktok.com/ZS2abcxyz/"
        vid3, platform3 = self.downloader.extract_video_id(tt_short)
        self.assertTrue(vid3.startswith("tt_"))
        self.assertEqual(platform3, "tiktok")

    def test_invalid_url_fails_gracefully(self):
        invalid_url = "https://www.youtube.com/shorts/INVALID_ID_NON_EXISTENT_9999"
        res = self.downloader.download_video(invalid_url, video_id="test_invalid")
        self.assertEqual(res["status"], "FAILED")
        self.assertTrue(len(res["error_message"]) > 0)
        self.assertEqual(res["file_path"], "")

    def test_cache_hit_skips_download(self):
        # Tạo file video giả lập để kiểm tra cơ chế cache
        dummy_file = os.path.join(self.test_dir, "test_cache.mp4")
        with open(dummy_file, "wb") as f:
            f.write(b"0" * (1024 * 1024))  # 1 MB

        url = "https://www.youtube.com/shorts/kJQP7kiw5Fk"
        res = self.downloader.download_video(url, video_id="test_cache", force_reload=False)
        self.assertEqual(res["status"], "SKIPPED")
        self.assertEqual(res["file_path"], dummy_file)
        self.assertGreaterEqual(res["file_size_mb"], 0.9)


if __name__ == "__main__":
    unittest.main()
