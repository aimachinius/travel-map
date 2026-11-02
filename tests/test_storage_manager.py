"""
Module test_storage_manager: Kiểm thử độc lập Module 5 - StorageManager (Cache JSON & TTL Cleanup).
"""

import os
import time
import unittest
import shutil

from src.server.services.storage_manager import StorageManager


class TestStorageManager(unittest.TestCase):
    def setUp(self):
        self.test_storage_dir = os.path.join(os.path.dirname(__file__), "fixtures", "test_storage")
        os.makedirs(self.test_storage_dir, exist_ok=True)
        self.manager = StorageManager(self.test_storage_dir)

    def tearDown(self):
        if os.path.exists(self.test_storage_dir):
            shutil.rmtree(self.test_storage_dir, ignore_errors=True)

    def test_cache_save_and_retrieve(self):
        sample_url = "https://www.youtube.com/shorts/sample123"
        sample_data = {
            "success": True,
            "restaurant": {"name": "Quán Cơm Quê", "address": "123 Đường 2/9"}
        }

        # Lưu cache
        self.manager.save_cache_result(sample_url, sample_data)

        # Đọc lại từ cache
        cached = self.manager.get_cached_result(sample_url)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["restaurant"]["name"], "Quán Cơm Quê")

    def test_safe_remove_file(self):
        dummy_file = os.path.join(self.test_storage_dir, "to_delete.txt")
        with open(dummy_file, "w") as f:
            f.write("test delete")

        self.assertTrue(os.path.exists(dummy_file))
        res = self.manager.safe_remove_file(dummy_file)
        self.assertTrue(res)
        time.sleep(0.1)
        self.assertFalse(os.path.exists(dummy_file))

    def test_clean_expired_files_ttl(self):
        # 1. Tạo file mới (tuổi thọ 0h)
        new_file = os.path.join(self.manager.videos_dir, "new_video.mp4")
        with open(new_file, "wb") as f:
            f.write(b"0" * 1024)

        # 2. Tạo file cũ (chỉnh sửa mtime về 48 giờ trước)
        old_file = os.path.join(self.manager.videos_dir, "old_video.mp4")
        with open(old_file, "wb") as f:
            f.write(b"0" * 2048)
        two_days_ago = time.time() - (48 * 3600)
        os.utime(old_file, (two_days_ago, two_days_ago))

        # Dọn rác với TTL = 24h
        clean_res = self.manager.clean_expired_files(ttl_hours=24, max_storage_mb=5000)

        self.assertGreaterEqual(clean_res["deleted_count"], 1)
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(new_file))

    def test_save_clean_keyframes(self):
        from PIL import Image
        import numpy as np

        img_pil = Image.new("RGB", (64, 64), color="blue")
        img_np = np.zeros((64, 64, 3), dtype=np.uint8)

        urls = self.manager.save_clean_keyframes("vid_test_123", [img_pil, img_np])
        self.assertEqual(len(urls), 2)
        self.assertEqual(urls[0], "/api/v1/keyframes/vid_test_123/frame_00.jpg")
        self.assertEqual(urls[1], "/api/v1/keyframes/vid_test_123/frame_01.jpg")

        saved_path_0 = os.path.join(self.manager.keyframes_dir, "vid_test_123", "frame_00.jpg")
        saved_path_1 = os.path.join(self.manager.keyframes_dir, "vid_test_123", "frame_01.jpg")
        self.assertTrue(os.path.exists(saved_path_0))
        self.assertTrue(os.path.exists(saved_path_1))


if __name__ == "__main__":
    unittest.main()
