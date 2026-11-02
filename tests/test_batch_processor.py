"""
Module test_batch_processor: Kiểm thử chế độ BatchProcessor, bổ sung cột nguồn_tên_quán, nguồn_địa_chỉ và cơ chế lưu định kỳ sau mỗi 10 mẫu.
"""

import os
import csv
import json
import shutil
import unittest
from unittest.mock import MagicMock

from src.batch.batch_processor import BatchProcessor
from src.pipeline.restaurant_pipeline import RestaurantExtractionResult, RestaurantExtractorPipeline
from src.config.settings import PipelineConfig


class TestBatchProcessor(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "fixtures", "test_batch_workspace")
        os.makedirs(self.test_dir, exist_ok=True)
        self.output_dir = os.path.join(self.test_dir, "output")
        self.videos_dir = os.path.join(self.test_dir, "videos")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.videos_dir, exist_ok=True)

        self.config = PipelineConfig(
            default_output_dir=self.output_dir,
            default_videos_dir=self.videos_dir,
            batch_save_interval=10,
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_restaurant_extraction_result_has_source_fields(self):
        res = RestaurantExtractionResult(
            video_id="12345",
            restaurant_name="Lẩu Tôm Bầu",
            address="17 Đống Đa, Đà Nẵng",
            nguồn_tên_quán="Frame 1 (OCR)",
            nguồn_địa_chỉ="Lời thoại (Script)",
            log_detect="[Frame 1/2] -> Tên OCR: Lẩu Tôm Bầu\n[Frame 2/2] -> Địa chỉ OCR: 17 Đống Đa",
        )
        d = res.to_dict()
        self.assertEqual(d["nguồn_tên_quán"], "Frame 1 (OCR)")
        self.assertEqual(d["nguồn_địa_chỉ"], "Lời thoại (Script)")
        self.assertIn("Lẩu Tôm Bầu", d["log_detect"])

    def test_export_results_to_csv_columns(self):
        processor = BatchProcessor(config=self.config)
        mock_results = [
            {
                "video_id": "vid_01",
                "restaurant_name": "Phở Bát Đàn",
                "address": "49 Bát Đàn, Hà Nội",
                "nguồn_tên_quán": "Frame 1 (OCR)",
                "nguồn_địa_chỉ": "Lời thoại (Script)",
                "log_detect": "[Frame 1/3] -> Tên OCR: Phở Bát Đàn\n[Frame 2/3] -> Địa chỉ OCR: 49 Bát Đàn",
                "status": "SUCCESS",
                "selected_frames_count": 3,
                "frames_dir": "vid_01/frames",
                "execution_time_sec": 4.5,
                "error_message": None,
            },
            {
                "video_id": "vid_02",
                "restaurant_name": "Bánh Mì Phượng",
                "address": "2B Phan Chu Trinh",
                "nguồn_tên_quán": "Frame 2 (OCR)",
                "nguồn_địa_chỉ": "Frame 2 (OCR)",
                "log_detect": "[Frame 1/2] -> Tên OCR: None\n[Frame 2/2] -> Tên OCR: Bánh Mì Phượng",
                "status": "SUCCESS",
                "selected_frames_count": 2,
                "frames_dir": "vid_02/frames",
                "execution_time_sec": 3.8,
                "error_message": None,
            }
        ]

        csv_path = os.path.join(self.output_dir, "batch_results.csv")
        processor._export_results_to_csv(mock_results, csv_path)

        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            self.assertIn("nguồn_tên_quán", headers)
            self.assertIn("nguồn_địa_chỉ", headers)
            self.assertIn("log_detect", headers)

            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["restaurant_name"], "Phở Bát Đàn")
            self.assertEqual(rows[0]["nguồn_tên_quán"], "Frame 1 (OCR)")
            self.assertEqual(rows[0]["nguồn_địa_chỉ"], "Lời thoại (Script)")
            self.assertIn("Phở Bát Đàn", rows[0]["log_detect"])

            self.assertEqual(rows[1]["restaurant_name"], "Bánh Mì Phượng")
            self.assertEqual(rows[1]["nguồn_tên_quán"], "Frame 2 (OCR)")
            self.assertEqual(rows[1]["nguồn_địa_chỉ"], "Frame 2 (OCR)")
            self.assertIn("Bánh Mì Phượng", rows[1]["log_detect"])

    def test_periodic_saving_checkpoint(self):
        # Tạo file CSV danh sách 25 mẫu test
        csv_file = os.path.join(self.test_dir, "test_list.csv")
        with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["video_id", "text"])
            for i in range(1, 26):
                writer.writerow([f"vid_{i:02d}", f"Kịch bản video {i}"])

        # Tạo giả lập các file mp4
        for i in range(1, 26):
            v_path = os.path.join(self.videos_dir, f"vid_{i:02d}.mp4")
            with open(v_path, "wb") as f:
                f.write(b"dummy")

        mock_pipeline = MagicMock(spec=RestaurantExtractorPipeline)

        def mock_process_video(video_path, script, video_id):
            return RestaurantExtractionResult(
                video_id=video_id,
                restaurant_name=f"Quán {video_id}",
                address=f"Địa chỉ {video_id}",
                nguồn_tên_quán="Frame 1 (OCR)",
                nguồn_địa_chỉ="Lời thoại (Script)",
                status="SUCCESS",
                execution_time_sec=0.1,
            )

        mock_pipeline.process_video.side_effect = mock_process_video

        processor = BatchProcessor(pipeline=mock_pipeline, config=self.config)
        # Giả lập save_interval=10 (lưu định kỳ mỗi 10 mẫu)
        res = processor.process_from_csv(
            csv_path=csv_file,
            videos_dir=self.videos_dir,
            output_dir=self.output_dir,
            save_interval=10,
        )

        self.assertEqual(res["summary"]["total_items"], 25)
        self.assertEqual(res["summary"]["processed_success"], 25)

        # Kiểm tra file CSV cuối cùng có đủ 25 dòng và 2 cột mới
        csv_path = os.path.join(self.output_dir, "batch_results.csv")
        self.assertTrue(os.path.exists(csv_path))

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            self.assertIn("nguồn_tên_quán", reader.fieldnames)
            self.assertIn("nguồn_địa_chỉ", reader.fieldnames)
            self.assertIn("log_detect", reader.fieldnames)
            rows = list(reader)
            self.assertEqual(len(rows), 25)
            self.assertEqual(rows[0]["nguồn_tên_quán"], "Frame 1 (OCR)")
            self.assertEqual(rows[0]["nguồn_địa_chỉ"], "Lời thoại (Script)")
            self.assertIsNotNone(rows[0]["log_detect"])

    def test_batch_start_index_preserves_previous_results(self):
        csv_file = os.path.join(self.test_dir, "test_resume.csv")
        with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["video_id", "text"])
            for i in range(1, 21):
                writer.writerow([f"vid_{i:02d}", f"Kịch bản video {i}"])

        for i in range(1, 21):
            v_path = os.path.join(self.videos_dir, f"vid_{i:02d}.mp4")
            with open(v_path, "wb") as f:
                f.write(b"dummy")

        mock_pipeline = MagicMock(spec=RestaurantExtractorPipeline)
        mock_pipeline.process_video.side_effect = lambda video_path, script, video_id: RestaurantExtractionResult(
            video_id=video_id,
            restaurant_name=f"Quán {video_id}",
            address=f"Địa chỉ {video_id}",
            status="SUCCESS",
        )

        processor = BatchProcessor(pipeline=mock_pipeline, config=self.config)

        # Lần 1: Chạy 5 mẫu đầu (index 0 đến 4)
        res1 = processor.process_from_csv(
            csv_path=csv_file,
            videos_dir=self.videos_dir,
            output_dir=self.output_dir,
            start_index=0,
            limit=5,
        )
        self.assertEqual(res1["summary"]["processed_success"], 5)

        # Lần 2: Chạy từ index 5, thêm 5 mẫu tiếp theo
        res2 = processor.process_from_csv(
            csv_path=csv_file,
            videos_dir=self.videos_dir,
            output_dir=self.output_dir,
            start_index=5,
            limit=5,
        )
        self.assertEqual(res2["summary"]["processed_success"], 5)

        # File batch_results.csv phải chứa đủ 10 mẫu (không bị xóa 5 mẫu đầu)
        csv_path = os.path.join(self.output_dir, "batch_results.csv")
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 10)
            self.assertEqual(rows[0]["video_id"], "vid_01")
            self.assertEqual(rows[4]["video_id"], "vid_05")
            self.assertEqual(rows[5]["video_id"], "vid_06")
            self.assertEqual(rows[9]["video_id"], "vid_10")

    def test_batch_start_video_id(self):
        csv_file = os.path.join(self.test_dir, "test_vid_id.csv")
        with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["video_id", "text"])
            for i in range(1, 11):
                writer.writerow([f"vid_{i:02d}", f"Kịch bản {i}"])

        for i in range(1, 11):
            v_path = os.path.join(self.videos_dir, f"vid_{i:02d}.mp4")
            with open(v_path, "wb") as f:
                f.write(b"dummy")

        mock_pipeline = MagicMock(spec=RestaurantExtractorPipeline)
        mock_pipeline.process_video.side_effect = lambda video_path, script, video_id: RestaurantExtractionResult(
            video_id=video_id,
            restaurant_name=f"Quán {video_id}",
            address=f"Địa chỉ {video_id}",
            status="SUCCESS",
        )

        processor = BatchProcessor(pipeline=mock_pipeline, config=self.config)
        # Bắt đầu từ vid_06
        res = processor.process_from_csv(
            csv_path=csv_file,
            videos_dir=self.videos_dir,
            output_dir=self.output_dir,
            start_video_id="vid_06",
            limit=3,
        )
        processed_vids = [r["video_id"] for r in res["results"]]
        self.assertEqual(processed_vids, ["vid_06", "vid_07", "vid_08"])

    def test_batch_resume(self):
        csv_file = os.path.join(self.test_dir, "test_auto_resume.csv")
        with open(csv_file, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["video_id", "text"])
            for i in range(1, 11):
                writer.writerow([f"vid_{i:02d}", f"Kịch bản {i}"])

        for i in range(1, 11):
            v_path = os.path.join(self.videos_dir, f"vid_{i:02d}.mp4")
            with open(v_path, "wb") as f:
                f.write(b"dummy")

        mock_pipeline = MagicMock(spec=RestaurantExtractorPipeline)
        mock_pipeline.process_video.side_effect = lambda video_path, script, video_id: RestaurantExtractionResult(
            video_id=video_id,
            restaurant_name=f"Quán {video_id}",
            address=f"Địa chỉ {video_id}",
            status="SUCCESS",
        )

        processor = BatchProcessor(pipeline=mock_pipeline, config=self.config)

        # Lần 1: Chạy 3 mẫu
        processor.process_from_csv(
            csv_path=csv_file,
            videos_dir=self.videos_dir,
            output_dir=self.output_dir,
            limit=3,
        )

        # Lần 2: resume=True, limit=2 -> phải tự động chạy vid_04 và vid_05
        res = processor.process_from_csv(
            csv_path=csv_file,
            videos_dir=self.videos_dir,
            output_dir=self.output_dir,
            resume=True,
            limit=2,
        )
        # Tổng kết quả tích lũy là 5 mẫu
        self.assertEqual(len(res["results"]), 5)
        all_vids = [r["video_id"] for r in res["results"]]
        self.assertEqual(all_vids, ["vid_01", "vid_02", "vid_03", "vid_04", "vid_05"])


if __name__ == "__main__":
    unittest.main()
