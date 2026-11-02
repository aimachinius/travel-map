"""
Module test_server_pipeline: Kiểm thử độc lập Module 6 - ServerExtractionPipeline (Pure Vision v3.0).
"""

import os
import unittest
import shutil
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image

from src.server.services.server_pipeline import ServerExtractionPipeline
from src.detectors.frame_selector import FrameCandidate
from src.config.settings import ServerConfig


class TestServerPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "fixtures", "test_pipeline_storage")
        os.makedirs(self.test_dir, exist_ok=True)
        self.config = ServerConfig(
            storage_dir=self.test_dir,
            tunnel_provider="none",
        )
        self.pipeline = ServerExtractionPipeline(config=self.config, lazy_load_models=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pipeline_cached_url(self):
        test_url = "https://www.youtube.com/shorts/test_cache_hit_123"
        mock_result = {
            "success": True,
            "status": "SUCCESS",
            "data": {
                "restaurant": {"name": "Phở Gia Truyền", "address": "49 Bát Đàn"},
            }
        }
        # Lưu trước vào cache
        self.pipeline.storage_manager.save_cache_result(test_url, mock_result)

        # Chạy pipeline với url đó, phải trả về ngay từ cache
        res = self.pipeline.process_url(test_url, force_reload=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["restaurant"]["name"], "Phở Gia Truyền")

    def test_pipeline_invalid_url_fails_gracefully(self):
        invalid_url = "https://www.youtube.com/shorts/INVALID_NON_EXISTENT_URL_0000"
        res = self.pipeline.process_url(invalid_url)
        self.assertFalse(res["success"])
        self.assertIn("error_message", res)

    def test_pipeline_pure_vision_flow_mock(self):
        test_url = "https://www.tiktok.com/@foodreview/video/123456789"
        dummy_video_file = os.path.join(self.test_dir, "test_vid.mp4")
        with open(dummy_video_file, "wb") as f:
            f.write(b"dummy mp4 content")

        # Mock downloader
        self.pipeline.downloader.download_video = MagicMock(return_value={
            "status": "SUCCESS",
            "file_path": dummy_video_file,
            "video_id": "vid_mock_123",
            "platform": "tiktok",
            "file_size_mb": 1.5,
            "duration": 30.0,
            "source_url": test_url,
        })

        # Mock Frame Candidate
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cand = FrameCandidate(
            scene_index=1,
            middle_frame=15,
            middle_time_sec=1.5,
            middle_time_str="00:01.500",
            metrics={"composite_score": 0.88, "box_count": 2, "avg_score": 0.9, "text_area_ratio": 0.05, "final_score": 1.1},
            frame_bgr=dummy_frame,
        )
        kf_stats = {
            "decode_time_sec": 1.15,
            "dbnet_time_sec": 0.45,
            "scoring_time_sec": 0.12,
            "sampled_candidates": 25,
            "dbnet_evaluated_frames_count": 20,
            "selected_top_k_count": 1,
        }

        # Mock Frame Selector (trả về candidates, kf_stats)
        self.pipeline.frame_selector.select_keyframes = MagicMock(return_value=([cand], kf_stats))
        self.pipeline.frame_selector.export_drawn_frames = MagicMock(return_value=[])

        # Mock VLM Extractor (Pure Vision analyze_frames)
        mock_vlm = MagicMock()
        mock_vlm.analyze_frames.return_value = {
            "tên_quán": "Bánh Canh Ghẹ 69",
            "địa_chỉ": "69 Nguyễn Tri Phương",
            "confidence_status": "Cao",
            "evidence": {
                "name_source": "Frame 1 (OCR)",
                "address_source": "Frame 1 (OCR)"
            },
            "chi_tiết_frames": [
                {
                    "frame_idx": 15,
                    "temporal_zone": "intro",
                    "timestamp_sec": 1.5,
                    "final_score": 1.1,
                    "ocr_name": "Bánh Canh Ghẹ 69",
                    "ocr_address": "69 Nguyễn Tri Phương",
                    "ocr_other": "Mở cửa 10h - 22h",
                }
            ],
        }
        self.pipeline.vlm_extractor = mock_vlm

        # Thực thi pipeline
        res = self.pipeline.process_url(test_url, force_reload=True, keep_raw_video=False)

        self.assertTrue(res["success"])
        data = res["data"]
        self.assertEqual(data["restaurant"]["name"], "Bánh Canh Ghẹ 69")
        self.assertEqual(data["restaurant"]["address"], "69 Nguyễn Tri Phương")
        self.assertEqual(data["restaurant"]["confidence_status"], "Cao")
        self.assertEqual(data["restaurant"]["evidence"]["name_source"], "Frame 1 (OCR)")

        # Kiểm tra metrics Pure Vision v3.0
        metrics = data["execution_metrics"]
        self.assertIn("video_decode_sampling_time_sec", metrics)
        self.assertIn("dbnet_gpu_inference_time_sec", metrics)
        self.assertIn("keyframe_total_time_sec", metrics)
        self.assertIn("vlm_sequential_inference_time_sec", metrics)
        self.assertEqual(metrics["video_decode_sampling_time_sec"], 1.15)
        self.assertEqual(metrics["dbnet_gpu_inference_time_sec"], 0.45)

        # Kiểm tra chi tiết frame OCR
        self.assertEqual(len(data["frames_ocr_details"]), 1)
        self.assertEqual(data["frames_ocr_details"][0]["ocr_name"], "Bánh Canh Ghẹ 69")
        self.assertEqual(data["frames_ocr_details"][0]["ocr_address"], "69 Nguyễn Tri Phương")
        self.assertEqual(data["frames_ocr_details"][0]["ocr_other"], "Mở cửa 10h - 22h")
        self.assertIn("/api/v1/keyframes/vid_mock_123/frame_00.jpg", data["frames_ocr_details"][0]["image_url"])


if __name__ == "__main__":
    unittest.main()
