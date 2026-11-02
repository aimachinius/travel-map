"""
Module scene_detector: Bộ lấy mẫu khung hình một lượt không giải mã dư thừa (FastSinglePassSampler v3.0).
Hoàn toàn thay thế PySceneDetect và loại bỏ lệnh nhảy cap.set() ngẫu nhiên.
Sử dụng vòng lặp tuần tự cap.grab() kết hợp cổng lọc biến thiên ảnh thu nhỏ 64x64 và lấy mẫu thích ứng 2 vùng:
- 0% -> 80% (Thân video): Bước nhảy 0.75s
- 80% -> 100% (Đuôi video): Bước nhảy 0.35s (hạ ngưỡng diff 50% để bắt nhạy card địa chỉ cuối video)
"""

import os
import time
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import cv2
import numpy as np

from ..utils.io_utils import format_timestamp
from ..utils.logger import get_logger

logger = get_logger("SceneDetector")


@dataclass
class RawSampledFrame:
    frame_idx: int
    timestamp_sec: float
    norm_time: float
    frame_bgr: np.ndarray
    sharpness: float


class FastSinglePassSampler:
    """
    Bộ lấy mẫu khung hình 1 lượt duy nhất (Single-Pass Sequential Grab):
    - Không dùng PySceneDetect quét toàn bộ video.
    - Không dùng cap.set() gây seek ngẫu nhiên trên H.264 GOP.
    - Kết hợp lấy mẫu thưa ở 0-80% đầu video, lấy mẫu dày ở 80-100% cuối video,
      và lọc trùng lặp tức thì bằng ảnh thu nhỏ 64x64.
    """
    def __init__(
        self,
        body_interval_sec: float = 0.75,
        tail_interval_sec: float = 0.35,
        tail_start_ratio: float = 0.80,
        visual_diff_thresh: float = 4.5,
        max_force_interval_sec: float = 2.5,
    ):
        self.body_interval_sec = body_interval_sec
        self.tail_interval_sec = tail_interval_sec
        self.tail_start_ratio = tail_start_ratio
        self.visual_diff_thresh = visual_diff_thresh
        self.max_force_interval_sec = max_force_interval_sec

    def sample_video(self, video_path: str) -> Tuple[List[RawSampledFrame], Dict[str, Any]]:
        t0 = time.time()
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Không thể mở file video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        step_body = max(1, int(round(self.body_interval_sec * fps)))
        step_tail = max(1, int(round(self.tail_interval_sec * fps)))
        tail_start_idx = int(total_frames * self.tail_start_ratio) if total_frames > 0 else 999999

        sampled: List[RawSampledFrame] = []
        prev_thumb: Optional[np.ndarray] = None
        last_kept_sec: float = -999.0
        frame_idx = 0

        while True:
            ret = cap.grab()
            if not ret:
                break

            is_tail = (total_frames > 0 and frame_idx >= tail_start_idx)
            step = step_tail if is_tail else step_body

            if frame_idx % step == 0:
                ok, frame_bgr = cap.retrieve()
                if ok and frame_bgr is not None:
                    curr_sec = frame_idx / fps
                    thumb = cv2.resize(frame_bgr, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)

                    keep = False
                    if prev_thumb is None:
                        keep = True
                    else:
                        diff = float(np.mean(np.abs(thumb - prev_thumb)))
                        # Ở vùng Outro (tail), hạ ngưỡng diff xuống 50% để bắt nhạy sự xuất hiện của text card
                        eff_thresh = self.visual_diff_thresh * (0.5 if is_tail else 1.0)
                        if diff >= eff_thresh or (curr_sec - last_kept_sec) >= self.max_force_interval_sec:
                            keep = True

                    if keep:
                        gray_small = cv2.cvtColor(thumb.astype(np.uint8), cv2.COLOR_BGR2GRAY)
                        sharpness = float(cv2.Laplacian(gray_small, cv2.CV_64F).var())
                        norm_t = min(1.0, frame_idx / max(1, total_frames - 1)) if total_frames > 0 else 0.0
                        sampled.append(
                            RawSampledFrame(
                                frame_idx=frame_idx,
                                timestamp_sec=round(curr_sec, 2),
                                norm_time=norm_t,
                                frame_bgr=frame_bgr,
                                sharpness=max(1.0, sharpness)
                            )
                        )
                        prev_thumb = thumb
                        last_kept_sec = curr_sec

            frame_idx += 1

        cap.release()

        # Cập nhật lại norm_time chính xác nếu header MP4 ban đầu báo sai total_frames
        actual_total = max(total_frames, frame_idx)
        for item in sampled:
            item.norm_time = min(1.0, item.frame_idx / max(1, actual_total - 1))

        stats = {
            "total_video_frames": actual_total,
            "fps": round(fps, 2),
            "sampled_candidates": len(sampled),
            "decode_time_sec": round(time.time() - t0, 3)
        }
        logger.info(
            f"FastSinglePassSampler hoàn tất: {len(sampled)} frames từ {actual_total} tổng frames "
            f"trong {stats['decode_time_sec']:.3f}s"
        )
        return sampled, stats


# Lớp tương thích ngược cho kiến trúc v2 (HybridSceneDetector)
class HybridSceneDetector:
    """
    Wrapper tương thích ngược sử dụng FastSinglePassSampler bên dưới,
    loại bỏ 100% PySceneDetect nhưng vẫn cung cấp hàm detect_candidate_frames.
    """
    def __init__(
        self,
        threshold: float = 27.0,
        min_scene_len: int = 15,
        enable_tail_sampling: bool = True,
        tail_start_ratio: float = 0.80,
        tail_interval_sec: float = 0.35,
        min_frame_gap_sec: float = 0.25,
        **kwargs
    ):
        self.sampler = FastSinglePassSampler(
            body_interval_sec=0.75,
            tail_interval_sec=tail_interval_sec,
            tail_start_ratio=tail_start_ratio,
            visual_diff_thresh=4.5,
        )

    def get_video_metadata(self, video_path: str) -> Tuple[int, float]:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Không thể mở video: {video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
        cap.release()
        return total_frames, fps

    def detect_candidate_frames(self, video_path: str) -> Tuple[List[int], int, float]:
        sampled, stats = self.sampler.sample_video(video_path)
        indices = [f.frame_idx for f in sampled]
        return indices, stats["total_video_frames"], stats["fps"]


class SceneDetector(HybridSceneDetector):
    """
    Wrapper tương thích ngược cho các module cũ gọi SceneDetector.detect(video_path).
    """
    def __init__(self, detector_type: str = "fast_single_pass", **kwargs):
        super().__init__(**kwargs)
        self.detector_type = detector_type

    def detect(self, video_path: str) -> Dict[str, Any]:
        cand_indices, total_frames, fps = self.detect_candidate_frames(video_path)
        duration_sec = total_frames / fps if fps > 0 else 0.0

        scenes = []
        for idx, f_idx in enumerate(cand_indices, 1):
            s_time = f_idx / fps if fps > 0 else 0.0
            scenes.append({
                "scene_index": idx,
                "start_frame": max(0, f_idx - 5),
                "end_frame": min(total_frames, f_idx + 5),
                "middle_frame": f_idx,
                "middle_time_sec": round(s_time, 3),
                "middle_time_str": format_timestamp(s_time),
            })

        return {
            "video_path": video_path,
            "total_frames": total_frames,
            "fps": fps,
            "duration_sec": round(duration_sec, 3),
            "scenes": scenes,
        }
