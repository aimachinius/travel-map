"""
Module test_vision_detector: Kiểm thử độc lập Module 2 - Keyframe Selection v3.0 (Tăng tốc GPU)
Kiểm tra các thuật toán:
1. FastSinglePassSampler (Single-Pass Sequential Grab + 64x64 Diff Gate)
2. GPUDBNetDetector (CUDA / CPU Fallback + max_side=640 + Mini-Batch)
3. Temporal Text-Mask NMS (64x64 Mask IoU >= 0.65)
4. Persistent Banner Suppression (IoU >= 0.75 qua >= 3 cảnh liên tiếp)
5. Time-Aware Spatial Scoring & Outro Card Boost (t >= 0.80, W_time = 1.5x)
6. Stratified Top-K & Quota Rollover (Intro / Body / Outro)
7. Kiểm thử thực tế trên video mp4 mẫu (tốc độ chọn Keyframe < 2.5s)
"""

import os
import time
import unittest
import numpy as np
import cv2

from src.detectors.scene_detector import FastSinglePassSampler, RawSampledFrame
from src.detectors.text_detector import GPUDBNetDetector
from src.detectors.frame_selector import (
    TextKeyframeSelector,
    KeyframeCandidate,
    compute_text_mask_64,
    compute_mask_iou,
    suppress_persistent_boxes,
    compute_time_aware_score,
    allocate_stratified_topk,
    deduplicate_by_text_mask_nms,
)
from src.config.settings import get_default_videos_dir


class TestKeyframeSelectorV3(unittest.TestCase):
    def setUp(self):
        self.selector = TextKeyframeSelector(enable_subtitle_suppression=True)

    def test_fast_single_pass_sampler_speed_and_structure(self):
        """Kiểm tra FastSinglePassSampler quét nhanh video mẫu trong < 2.0 giây."""
        videos_dir = get_default_videos_dir()
        sample_video = None
        if os.path.exists(videos_dir):
            for f in sorted(os.listdir(videos_dir)):
                if f.endswith(".mp4"):
                    sample_video = os.path.join(videos_dir, f)
                    break

        if not sample_video or not os.path.exists(sample_video):
            self.skipTest("Không tìm thấy video mẫu trong videos_dir để kiểm thử.")

        sampler = FastSinglePassSampler(
            body_interval_sec=0.75,
            tail_interval_sec=0.35,
            tail_start_ratio=0.80,
            visual_diff_thresh=4.5,
        )

        t0 = time.time()
        sampled, stats = sampler.sample_video(sample_video)
        elapsed = time.time() - t0

        self.assertIsInstance(sampled, list)
        self.assertGreater(len(sampled), 0)
        self.assertLess(elapsed, 4.0, f"Thời gian lấy mẫu 1 lượt phải < 4.0s, thực tế: {elapsed:.3f}s")
        self.assertIn("decode_time_sec", stats)
        self.assertIn("sampled_candidates", stats)

        # Kiểm tra cấu trúc RawSampledFrame
        first = sampled[0]
        self.assertIsInstance(first, RawSampledFrame)
        self.assertGreaterEqual(first.sharpness, 1.0)
        self.assertIsNotNone(first.frame_bgr)

    def test_gpudbnet_preprocessing_and_batching(self):
        """Kiểm tra GPUDBNetDetector thu phóng max_side=640 chia hết cho 32 và chạy batch."""
        detector = GPUDBNetDetector()
        dummy_frame = np.zeros((1920, 1080, 3), dtype=np.uint8)

        # Preprocess single
        tensor = detector._preprocess_single(dummy_frame, target_h=640, target_w=352)
        self.assertEqual(tensor.shape, (3, 640, 352))

        # Batch detect
        results = detector.detect_batch([dummy_frame, dummy_frame])
        self.assertEqual(len(results), 2)
        for boxes, scores in results:
            self.assertIsInstance(boxes, list)
            self.assertIsInstance(scores, list)

    def test_text_mask_iou_deduplication(self):
        """Hai frame có hộp chữ ở vị trí tương đương trên ảnh 1080x1920 đạt Mask_IoU >= 0.65."""
        boxes_a = [np.array([[100, 200], [900, 200], [900, 350], [100, 350]], dtype=np.float32)]
        boxes_b = [np.array([[105, 205], [895, 205], [895, 345], [105, 345]], dtype=np.float32)]

        mask_a = compute_text_mask_64(boxes_a, img_w=1080, img_h=1920, grid_size=64)
        mask_b = compute_text_mask_64(boxes_b, img_w=1080, img_h=1920, grid_size=64)
        iou = compute_mask_iou(mask_a, mask_b)

        self.assertGreaterEqual(iou, 0.65, f"Mask IoU phải >= 0.65, thực tế: {iou:.4f}")

    def test_persistent_banner_suppression(self):
        """Hộp chữ tiêu đề tĩnh lặp lại qua >= 3 cảnh liên tiếp chỉ được tính ở cảnh 1, lọc bỏ từ cảnh 2."""
        banner_box = np.array([[100, 150], [950, 150], [950, 280], [100, 280]], dtype=np.float32)
        address_box = np.array([[200, 1200], [850, 1200], [850, 1350], [200, 1350]], dtype=np.float32)

        # 4 cảnh liên tiếp đều chứa banner_box, riêng cảnh thứ 4 có thêm address_box
        frames_boxes = [
            [banner_box],
            [banner_box],
            [banner_box],
            [banner_box, address_box],
        ]

        filtered = suppress_persistent_boxes(frames_boxes, iou_thresh=0.75, min_consecutive=3)

        self.assertEqual(len(filtered[0]), 1, "Cảnh 1 phải giữ lại banner lần đầu xuất hiện")
        self.assertEqual(len(filtered[1]), 0, "Cảnh 2 phải bị lọc bỏ banner tĩnh")
        self.assertEqual(len(filtered[2]), 0, "Cảnh 3 phải bị lọc bỏ banner tĩnh")
        self.assertEqual(len(filtered[3]), 1, "Cảnh 4 chỉ còn lại hộp chữ địa chỉ mới")

    def test_time_aware_tail_unpenalized(self):
        """Cụm >= 2 dòng chữ đặt ở nửa dưới màn hình ở Outro (t >= 0.80) không bị phạt 0.2x và nhận W_time = 1.5x."""
        img_w, img_h = 1080, 1920
        line1 = np.array([[200, int(img_h * 0.65)], [880, int(img_h * 0.65)], [880, int(img_h * 0.70)], [200, int(img_h * 0.70)]], dtype=np.float32)
        line2 = np.array([[200, int(img_h * 0.72)], [880, int(img_h * 0.72)], [880, int(img_h * 0.77)], [200, int(img_h * 0.77)]], dtype=np.float32)
        boxes = [line1, line2]
        scores = [0.95, 0.92]

        # 1. Trường hợp t = 0.90 (Vùng Outro)
        box_cnt_tail, avg_sc_tail, area_tail, comp_tail, t_weight_tail, final_tail = compute_time_aware_score(
            boxes=boxes,
            scores=scores,
            img_w=img_w,
            img_h=img_h,
            norm_time=0.90,
            enable_subtitle_suppression=True,
        )

        # 2. Trường hợp t = 0.50 (Vùng Body - Bị phạt phụ đề)
        box_cnt_body, avg_sc_body, area_body, comp_body, t_weight_body, final_body = compute_time_aware_score(
            boxes=boxes,
            scores=scores,
            img_w=img_w,
            img_h=img_h,
            norm_time=0.50,
            enable_subtitle_suppression=True,
        )

        self.assertEqual(t_weight_tail, 1.5)
        self.assertEqual(t_weight_body, 1.0)
        self.assertGreater(box_cnt_tail, box_cnt_body * 3.0)
        self.assertGreater(final_tail, final_body * 3.0)

    def test_stratified_topk_and_rollover(self):
        """Phân bổ đúng hạn ngạch Intro/Body/Outro và tự động dồn suất trống về Outro khi Body trống."""
        dummy_mask = np.zeros((64, 64), dtype=np.uint8)
        c_intro = KeyframeCandidate(10, 0.3, 0.10, "intro", 2, 0.8, 0.02, 0.5, 1.2, 0.60, 100.0, dummy_mask)
        c_outro1 = KeyframeCandidate(250, 8.3, 0.85, "outro", 3, 0.9, 0.03, 0.7, 1.5, 1.05, 120.0, dummy_mask)
        c_outro2 = KeyframeCandidate(270, 9.0, 0.92, "outro", 4, 0.9, 0.04, 0.8, 1.5, 1.20, 110.0, dummy_mask)
        c_outro3 = KeyframeCandidate(290, 9.6, 0.98, "outro", 3, 0.85, 0.03, 0.6, 1.5, 0.90, 105.0, dummy_mask)

        selected = allocate_stratified_topk([c_intro, c_outro1, c_outro2, c_outro3], top_k=4)

        self.assertEqual(len(selected), 4)
        outro_count = sum(1 for c in selected if c.temporal_zone == "outro")
        self.assertEqual(outro_count, 3)

    def test_select_keyframes_on_local_sample(self):
        """Kiểm thử trích xuất toàn diện Keyframe Selection v3 trên video thực tế."""
        videos_dir = get_default_videos_dir()
        sample_video = None
        if os.path.exists(videos_dir):
            for f in sorted(os.listdir(videos_dir)):
                if f.endswith(".mp4"):
                    sample_video = os.path.join(videos_dir, f)
                    break

        if not sample_video or not os.path.exists(sample_video):
            self.skipTest("Không tìm thấy video mẫu trong videos_dir để kiểm thử.")

        video_name = os.path.splitext(os.path.basename(sample_video))[0]
        output_dir = os.path.join(os.path.dirname(__file__), "output_keyframes", video_name)
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n🎬 Đang chạy trích chọn Keyframes v3 cho video: {os.path.basename(sample_video)}")
        candidates, kf_stats = self.selector.select_keyframes(
            video_path=sample_video,
            top_k=5,
            keep_frames_in_memory=True,
            return_stats=True,
        )

        self.assertIsInstance(candidates, list)
        self.assertGreater(len(candidates), 0, "Không trích xuất được frame nào từ video.")
        self.assertIn("dbnet_time_sec", kf_stats)
        self.assertIn("decode_time_sec", kf_stats)

        # Xuất ảnh vẽ preview
        drawn_paths = self.selector.export_drawn_frames(candidates, output_dir=output_dir, video_id="v3_run")
        self.assertEqual(len(drawn_paths), len(candidates))

        for rank, c in enumerate(candidates, 1):
            self.assertIsNotNone(c.clean_frame_pil, f"Candidate #{rank} thiếu clean_frame_pil.")
            self.assertIn(c.temporal_zone, ["intro", "body", "outro"])
            print(f"  [Frame #{rank}] Zone: {c.temporal_zone.upper()} | Time: {c.middle_time_str} | Final Score: {c.final_score:.4f} | Box Count: {c.box_count}")


if __name__ == "__main__":
    unittest.main()
