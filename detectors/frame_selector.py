"""
Module frame_selector: Kiến trúc trích chọn và xếp hạng Keyframe v2 (Keyframe Selection v2).
Tích hợp:
1. Lấy mẫu lai Hybrid Sampling (PySceneDetect 0-80% + Tail Dense Sampling 80-100% 0.5s)
2. Lọc Banner tĩnh (Persistent Box Suppression IoU >= 0.75 qua >= 3 cảnh liên tiếp)
3. Khử trùng lặp bố cục chữ (Temporal Text-Mask NMS 64x64, Mask IoU >= 0.65)
4. Chấm điểm Không gian phụ thuộc Thời gian (Time-Aware Spatial Scoring & Outro Boost 1.5x)
5. Phân bổ Top-K Phân tầng theo hạn ngạch (Stratified Top-K: Intro / Body / Outro & Quota Rollover)
"""

import os
import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image

from .scene_detector import FastSinglePassSampler, RawSampledFrame, HybridSceneDetector, SceneDetector
from .text_detector import GPUDBNetDetector, ONNXTextDetector
from ..utils.io_utils import cv2_imwrite, draw_detection_boxes, format_timestamp
from ..utils.logger import get_logger

logger = get_logger("TextKeyframeSelector")


class KeyframeCandidate:
    """
    Thông tin khung hình ứng viên chuẩn hóa theo kiến trúc Keyframe Selection v2.
    Hỗ trợ cả khởi tạo vị trí (positional) v2 và từ khóa (keyword) tương thích ngược.
    """
    def __init__(
        self,
        frame_idx: int = 0,
        timestamp_sec: float = 0.0,
        norm_time: float = 0.0,
        temporal_zone: str = "body",
        box_count_eff: float = 0.0,
        avg_score_eff: float = 0.0,
        area_ratio_eff: float = 0.0,
        composite_score: float = 0.0,
        time_weight: float = 1.0,
        final_score: float = 0.0,
        sharpness_score: float = 0.0,
        text_mask_64: Optional[np.ndarray] = None,
        clean_frame_pil: Optional[Image.Image] = None,
        frame_bgr: Optional[np.ndarray] = None,
        metrics: Optional[Dict[str, Any]] = None,
        scene_index: int = 1,
        # Tham số từ khóa tương thích ngược:
        middle_frame: Optional[int] = None,
        middle_time_sec: Optional[float] = None,
        middle_time_str: Optional[str] = None,
        **kwargs
    ):
        self.frame_idx = middle_frame if middle_frame is not None else frame_idx
        self.timestamp_sec = middle_time_sec if middle_time_sec is not None else timestamp_sec
        self.norm_time = norm_time
        self.temporal_zone = temporal_zone
        self.clean_frame_pil = clean_frame_pil
        self.frame_bgr = frame_bgr
        self.metrics = dict(metrics) if metrics is not None else {}
        self.scene_index = scene_index
        self.sharpness_score = sharpness_score
        self.text_mask_64 = text_mask_64 if text_mask_64 is not None else np.zeros((64, 64), dtype=np.uint8)

        if metrics:
            self.composite_score = float(metrics.get("composite_score", composite_score))
            self.box_count_eff = float(metrics.get("box_count", box_count_eff))
            self.avg_score_eff = float(metrics.get("avg_score", avg_score_eff))
            self.area_ratio_eff = float(metrics.get("text_area_ratio", area_ratio_eff))
            self.final_score = float(metrics.get("final_score", final_score or self.composite_score))
        else:
            self.composite_score = composite_score
            self.box_count_eff = box_count_eff
            self.avg_score_eff = avg_score_eff
            self.area_ratio_eff = area_ratio_eff
            self.final_score = final_score

        self.time_weight = time_weight
        self._middle_time_str = middle_time_str

        # Tự động tạo clean_frame_pil từ frame_bgr nếu có
        if self.clean_frame_pil is None and self.frame_bgr is not None:
            rgb = cv2.cvtColor(self.frame_bgr, cv2.COLOR_BGR2RGB)
            self.clean_frame_pil = Image.fromarray(rgb)

    # --- Các thuộc tính tương thích ngược (Backward Compatibility) ---
    @property
    def middle_frame(self) -> int:
        return self.frame_idx

    @property
    def middle_time_sec(self) -> float:
        return self.timestamp_sec

    @property
    def middle_time_str(self) -> str:
        if self._middle_time_str:
            return self._middle_time_str
        return format_timestamp(self.timestamp_sec)

    @property
    def box_count(self) -> int:
        return int(round(self.box_count_eff))

    @property
    def avg_score(self) -> float:
        return float(self.avg_score_eff)

    @property
    def text_area_ratio(self) -> float:
        return float(self.area_ratio_eff)



# Alias tương thích ngược cho FrameCandidate
FrameCandidate = KeyframeCandidate


def polygon_to_bbox(poly: np.ndarray) -> Tuple[float, float, float, float]:
    """Chuyển polygon 4 điểm (4, 2) về bounding box chuẩn (x_min, y_min, x_max, y_max)."""
    pts = np.asarray(poly, dtype=np.float32)
    return float(np.min(pts[:, 0])), float(np.min(pts[:, 1])), float(np.max(pts[:, 0])), float(np.max(pts[:, 1]))


def compute_box_iou(poly_a: np.ndarray, poly_b: np.ndarray) -> float:
    """Tính IoU giữa 2 hộp chữ dựa trên Axis-Aligned Bounding Box."""
    ax1, ay1, ax2, ay2 = polygon_to_bbox(poly_a)
    bx1, by1, bx2, by2 = polygon_to_bbox(poly_b)

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area
    if union_area <= 1e-6:
        return 0.0
    return inter_area / union_area


def suppress_persistent_boxes(
    all_frames_boxes: List[List[np.ndarray]],
    all_frames_scores: Optional[List[List[float]]] = None,
    iou_thresh: float = 0.75,
    min_consecutive: int = 3,
) -> Union[Tuple[List[List[np.ndarray]], List[List[float]]], List[List[np.ndarray]]]:
    """
    Loại bỏ các hộp chữ tĩnh (Static Banner / Watermark) xuất hiện lặp lại ở cùng tọa độ
    (IoU >= iou_thresh) xuyên suốt từ `min_consecutive` frame liên tiếp trở lên.
    Giữ lại ở lần xuất hiện đầu tiên, loại bỏ khỏi phép tính điểm từ frame thứ 2 của chuỗi.

    Nếu all_frames_scores được truyền vào, trả về (filtered_boxes, filtered_scores).
    Nếu all_frames_scores is None, trả về filtered_boxes.
    """
    has_scores = all_frames_scores is not None
    n_frames = len(all_frames_boxes)
    scores_internal = (
        all_frames_scores
        if has_scores
        else [[1.0] * len(boxes) for boxes in all_frames_boxes]
    )

    suppress_flags = [[False] * len(boxes) for boxes in all_frames_boxes]

    for t in range(n_frames):
        for i, box_t in enumerate(all_frames_boxes[t]):
            if suppress_flags[t][i]:
                continue
            matched_chain: List[Tuple[int, int]] = [(t, i)]
            curr_box = box_t

            for nxt in range(t + 1, n_frames):
                best_j = -1
                best_iou = 0.0
                for j, box_nxt in enumerate(all_frames_boxes[nxt]):
                    iou = compute_box_iou(curr_box, box_nxt)
                    if iou > best_iou:
                        best_iou = iou
                        best_j = j
                if best_j != -1 and best_iou >= iou_thresh:
                    matched_chain.append((nxt, best_j))
                    curr_box = all_frames_boxes[nxt][best_j]
                else:
                    break

            if len(matched_chain) >= min_consecutive:
                # Giữ ở frame đầu tiên matched_chain[0], loại bỏ từ matched_chain[1:]
                for f_idx, b_idx in matched_chain[1:]:
                    suppress_flags[f_idx][b_idx] = True

    filtered_boxes: List[List[np.ndarray]] = []
    filtered_scores: List[List[float]] = []
    for t in range(n_frames):
        f_boxes = [b for idx, b in enumerate(all_frames_boxes[t]) if not suppress_flags[t][idx]]
        f_scores = [s for idx, s in enumerate(scores_internal[t]) if not suppress_flags[t][idx]]
        filtered_boxes.append(f_boxes)
        filtered_scores.append(f_scores)

    if has_scores:
        return filtered_boxes, filtered_scores
    return filtered_boxes


def compute_text_mask_64(
    boxes: List[np.ndarray],
    img_w: int,
    img_h: int,
    grid_size: int = 64,
) -> np.ndarray:
    """Tạo mặt nạ nhị phân kích thước 64x64 đại diện cho bố cục chữ trên khung hình."""
    mask = np.zeros((grid_size, grid_size), dtype=np.uint8)
    if not boxes or img_w <= 0 or img_h <= 0:
        return mask

    scale_x = grid_size / float(img_w)
    scale_y = grid_size / float(img_h)

    for poly in boxes:
        x1, y1, x2, y2 = polygon_to_bbox(poly)
        gx1 = int(np.clip(math.floor(x1 * scale_x), 0, grid_size - 1))
        gy1 = int(np.clip(math.floor(y1 * scale_y), 0, grid_size - 1))
        gx2 = int(np.clip(math.ceil(x2 * scale_x), gx1 + 1, grid_size))
        gy2 = int(np.clip(math.ceil(y2 * scale_y), gy1 + 1, grid_size))
        mask[gy1:gy2, gx1:gx2] = 1

    return mask


def compute_mask_iou(mask_a: np.ndarray, mask_b: np.ndarray) -> float:
    """Tính độ trùng lặp Mask IoU giữa 2 mặt nạ bố cục chữ 64x64."""
    inter = int(np.sum((mask_a > 0) & (mask_b > 0)))
    union = int(np.sum((mask_a > 0) | (mask_b > 0)))
    if union == 0:
        return 0.0
    return float(inter) / float(union)


def has_multiline_info_cluster(boxes: List[np.ndarray], img_h: int) -> bool:
    """
    Kiểm tra xem trong frame có cụm >= 2 hộp chữ xếp dọc gần nhau (đặc trưng của card
    Tên quán + Địa chỉ + Giờ mở cửa ở cuối video) hay không.
    """
    if len(boxes) < 2 or img_h <= 0:
        return False

    y_centers = []
    for poly in boxes:
        _, y1, _, y2 = polygon_to_bbox(poly)
        y_centers.append(((y1 + y2) * 0.5) / float(img_h))

    y_centers.sort()
    for i in range(len(y_centers) - 1):
        if (y_centers[i + 1] - y_centers[i]) <= 0.14:
            return True
    return False


def get_temporal_zone(norm_time: float) -> str:
    if norm_time < 0.25:
        return "intro"
    elif norm_time < 0.75:
        return "body"
    return "outro"


def get_time_weight(norm_time: float) -> float:
    if norm_time <= 0.15:
        return 1.2
    elif norm_time >= 0.80:
        return 1.5
    return 1.0


def compute_time_aware_score(
    boxes: List[np.ndarray],
    scores: List[float],
    img_w: int,
    img_h: int,
    norm_time: float,
    enable_subtitle_suppression: bool = True,
) -> Tuple[float, float, float, float, float, float]:
    """
    Trả về: (box_count_eff, avg_score_eff, area_ratio_eff, composite_score, time_weight, final_score)
    """
    if not boxes or img_w <= 0 or img_h <= 0:
        tw = get_time_weight(norm_time)
        return 0.0, 0.0, 0.0, 0.0, tw, 0.0

    frame_area = float(img_w * img_h)
    is_tail_multiline = (norm_time >= 0.80) and has_multiline_info_cluster(boxes, img_h)

    weighted_box_count = 0.0
    weighted_score_sum = 0.0
    weighted_area_sum = 0.0

    for poly, sc in zip(boxes, scores):
        pts = np.asarray(poly, dtype=np.float32)
        poly_area = float(cv2.contourArea(pts))
        x1, y1, x2, y2 = polygon_to_bbox(pts)
        cx_norm = ((x1 + x2) * 0.5) / float(img_w)
        cy_norm = ((y1 + y2) * 0.5) / float(img_h)

        w_spatial = 1.0
        if enable_subtitle_suppression:
            # Vùng biển hiệu nửa trên
            if 0.05 <= cy_norm <= 0.55:
                w_spatial = 1.5
            # Vùng phụ đề tự động nửa dưới
            elif 0.60 <= cy_norm <= 0.90 and 0.15 <= cx_norm <= 0.85:
                if norm_time < 0.80:
                    w_spatial = 0.2
                else:
                    # Ở 20% cuối video: Gỡ phạt nếu là card nhiều dòng
                    w_spatial = 1.0 if is_tail_multiline else 0.3

        weighted_box_count += w_spatial
        weighted_score_sum += float(sc) * w_spatial
        weighted_area_sum += poly_area * w_spatial

    avg_score_eff = weighted_score_sum / max(weighted_box_count, 1e-6)
    area_ratio_eff = weighted_area_sum / frame_area

    composite_score = (
        avg_score_eff
        * (1.0 - math.exp(-15.0 * area_ratio_eff))
        * math.log(1.0 + max(0.0, weighted_box_count))
    )
    t_weight = get_time_weight(norm_time)
    final_score = composite_score * t_weight

    return weighted_box_count, avg_score_eff, area_ratio_eff, composite_score, t_weight, final_score


def deduplicate_by_text_mask_nms(
    candidates: List[KeyframeCandidate],
    mask_iou_thresh: float = 0.65,
) -> List[KeyframeCandidate]:
    """
    Khử trùng lặp các frame có bố cục chữ tương đồng (Mask IoU >= mask_iou_thresh).
    Ưu tiên giữ lại ứng viên có (final_score * hệ số sắc nét) cao hơn.
    """
    sorted_cands = sorted(
        candidates,
        key=lambda c: c.final_score * (1.0 + 0.05 * math.log1p(max(0.0, c.sharpness_score))),
        reverse=True,
    )
    kept: List[KeyframeCandidate] = []
    for cand in sorted_cands:
        is_dup = False
        for existing in kept:
            if compute_mask_iou(cand.text_mask_64, existing.text_mask_64) >= mask_iou_thresh:
                is_dup = True
                break
        if not is_dup:
            kept.append(cand)
    return kept


def allocate_stratified_topk(
    candidates: List[KeyframeCandidate],
    top_k: int = 4,
) -> List[KeyframeCandidate]:
    """
    Phân bổ Top-K theo hạn ngạch 3 phân vùng thời gian:
    - Intro (0% -> 25%): max(1, floor(0.20 * K))
    - Body (25% -> 75%): max(1, floor(0.25 * K))
    - Outro (75% -> 100%): Phần còn lại (ưu tiên cao nhất)
    Nếu một phân vùng thiếu ứng viên, suất trống tự động dồn sang Outro -> Intro -> Body.
    """
    if top_k <= 0 or not candidates:
        return []

    if len(candidates) <= top_k:
        return sorted(candidates, key=lambda c: c.frame_idx)

    k_intro = max(1, int(math.floor(0.20 * top_k))) if top_k >= 3 else 1
    k_body = max(1, int(math.floor(0.25 * top_k))) if top_k >= 3 else 0
    k_outro = max(1, top_k - k_intro - k_body)

    intro_pool = sorted([c for c in candidates if c.temporal_zone == "intro"], key=lambda x: x.final_score, reverse=True)
    body_pool = sorted([c for c in candidates if c.temporal_zone == "body"], key=lambda x: x.final_score, reverse=True)
    outro_pool = sorted([c for c in candidates if c.temporal_zone == "outro"], key=lambda x: x.final_score, reverse=True)

    selected: List[KeyframeCandidate] = []
    selected.extend(intro_pool[:k_intro])
    selected.extend(body_pool[:k_body])
    selected.extend(outro_pool[:k_outro])

    # Dồn suất trống (Quota Rollover) theo thứ tự ưu tiên: Outro -> Intro -> Body
    if len(selected) < top_k:
        selected_ids = {c.frame_idx for c in selected}
        rollover_pools = (
            outro_pool[k_outro:]
            + intro_pool[k_intro:]
            + body_pool[k_body:]
        )
        for cand in rollover_pools:
            if cand.frame_idx not in selected_ids:
                selected.append(cand)
                selected_ids.add(cand.frame_idx)
                if len(selected) == top_k:
                    break

    # Trả về theo thứ tự thời gian xuất hiện trong video
    return sorted(selected[:top_k], key=lambda c: c.frame_idx)


class TextKeyframeSelector:
    """
    Bộ điều phối trích xuất và lọc keyframe văn bản v3 (Tăng tốc GPU):
    - Lấy mẫu 1 lượt tuần tự bằng FastSinglePassSampler (cap.grab + lọc biến thiên 64x64).
    - Quét chữ bằng GPUDBNetDetector (CUDAExecutionProvider + max_side=640 + Mini-Batch).
    - Khử tiêu đề tĩnh (Persistent Box Suppression).
    - Chấm điểm Time-Aware Spatial Scoring (Outro Card Boost 1.5x).
    - Khử trùng lặp Text-Mask NMS 64x64.
    - Phân tầng hạn ngạch Stratified Top-K.
    """
    def __init__(
        self,
        det_model_path: Optional[str] = None,
        use_gpu: bool = True,
        dbnet_max_side: int = 640,
        dbnet_batch_size: int = 8,
        body_sample_interval_sec: float = 0.75,
        tail_sample_interval_sec: float = 0.35,
        tail_start_ratio: float = 0.80,
        visual_diff_thresh: float = 4.5,
        max_force_interval_sec: float = 2.5,
        persistent_box_iou_thresh: float = 0.75,
        persistent_min_consecutive_scenes: int = 3,
        persistent_min_consecutive_frames: Optional[int] = None,
        text_mask_iou_thresh: float = 0.65,
        min_avg_score: float = 0.40,
        min_text_area_ratio: float = 0.0005,
        enable_stratified_topk: bool = True,
        enable_subtitle_suppression: bool = True,
        scene_detector: Optional[Any] = None,
        text_detector: Optional[Any] = None,
        use_cpu_provider: bool = False,
        **kwargs
    ):
        if persistent_min_consecutive_frames is not None:
            persistent_min_consecutive_scenes = persistent_min_consecutive_frames

        # Khởi tạo Sampler lấy mẫu 1 lượt
        if scene_detector is not None:
            if hasattr(scene_detector, "sample_video"):
                self.sampler = scene_detector
            elif hasattr(scene_detector, "sampler"):
                self.sampler = scene_detector.sampler
            else:
                self.sampler = FastSinglePassSampler(
                    body_interval_sec=body_sample_interval_sec,
                    tail_interval_sec=tail_sample_interval_sec,
                    tail_start_ratio=tail_start_ratio,
                    visual_diff_thresh=visual_diff_thresh,
                    max_force_interval_sec=max_force_interval_sec,
                )
            self.scene_detector = scene_detector
        else:
            self.sampler = FastSinglePassSampler(
                body_interval_sec=body_sample_interval_sec,
                tail_interval_sec=tail_sample_interval_sec,
                tail_start_ratio=tail_start_ratio,
                visual_diff_thresh=visual_diff_thresh,
                max_force_interval_sec=max_force_interval_sec,
            )
            self.scene_detector = HybridSceneDetector()

        # Khởi tạo GPU DBNet Detector
        if text_detector is not None:
            self.text_detector = text_detector
        else:
            force_cpu = use_cpu_provider or (not use_gpu)
            self.text_detector = GPUDBNetDetector(
                model_path=det_model_path,
                max_side=dbnet_max_side,
                force_cpu=force_cpu,
            )

        self.dbnet_batch_size = dbnet_batch_size
        self.enable_subtitle_suppression = enable_subtitle_suppression
        self.persistent_box_iou_thresh = persistent_box_iou_thresh
        self.persistent_min_consecutive_scenes = persistent_min_consecutive_scenes
        self.text_mask_iou_thresh = text_mask_iou_thresh
        self.min_avg_score = min_avg_score
        self.min_text_area_ratio = min_text_area_ratio
        self.enable_stratified_topk = enable_stratified_topk

    def _apply_subtitle_suppression(
        self,
        metrics: Dict[str, Any],
        img_shape: Tuple[int, int],
        penalty_weight: float = 0.2,
        boost_weight: float = 1.5,
    ) -> Dict[str, Any]:
        """Phương thức tương thích ngược cho bộ lọc phụ đề TikTok."""
        dt_boxes = metrics.get("dt_boxes", [])
        scores = metrics.get("scores", [])
        if not dt_boxes:
            metrics["is_subtitle_filtered"] = False
            return metrics

        h, w = img_shape[:2]
        total_area = float(h * w) if (h * w) > 0 else 1.0

        effective_scores = []
        effective_mask = np.zeros((h, w), dtype=np.uint8)
        subtitle_detected = False

        for i, box in enumerate(dt_boxes):
            pts = np.array(box, dtype=np.float32)
            center_x = float(np.mean(pts[:, 0])) / w if w > 0 else 0.5
            center_y = float(np.mean(pts[:, 1])) / h if h > 0 else 0.5
            raw_score = float(scores[i]) if i < len(scores) else 0.5
            weight = 1.0

            if 0.60 <= center_y <= 0.90 and 0.15 <= center_x <= 0.85:
                weight = penalty_weight
                subtitle_detected = True
            elif 0.05 <= center_y <= 0.55:
                weight = boost_weight

            effective_score = min(raw_score * weight, 1.0)
            effective_scores.append(effective_score)
            if weight >= 0.5:
                cv2.fillPoly(effective_mask, [pts.astype(np.int32)], 1)

        effective_area = float(np.sum(effective_mask))
        effective_area_ratio = effective_area / total_area
        effective_avg_score = float(np.mean(effective_scores)) if effective_scores else 0.0
        effective_box_count = len([s for s in effective_scores if s >= 0.3])
        effective_composite = effective_avg_score * (1.0 - np.exp(-15.0 * effective_area_ratio)) * np.log1p(effective_box_count)

        rescored_metrics = dict(metrics)
        rescored_metrics["composite_score"] = round(float(effective_composite), 4)
        rescored_metrics["effective_avg_score"] = round(float(effective_avg_score), 4)
        rescored_metrics["effective_area_ratio"] = round(float(effective_area_ratio), 6)
        rescored_metrics["is_subtitle_filtered"] = subtitle_detected
        return rescored_metrics

    def select_keyframes(
        self,
        video_path: str,
        top_k: int = 5,
        keep_frames_in_memory: bool = True,
        return_stats: bool = False,
        **kwargs
    ) -> Union[Tuple[List[KeyframeCandidate], Dict[str, Any]], List[KeyframeCandidate]]:
        """
        Quy trình xử lý hoàn chỉnh theo kiến trúc Keyframe Selection v3 (Tăng tốc GPU):
        1. FastSinglePassSampler: Lấy mẫu 1 lượt tuần tự (cap.grab + lọc biến thiên 64x64).
        2. GPUDBNetDetector: Quét chữ theo lô Mini-Batch trên GPU (<0.6s).
        3. Khử banner/watermark tĩnh lặp lại qua >= 3 cảnh liên tiếp.
        4. Chấm điểm Time-Aware Spatial Scoring & Outro Card Boost.
        5. Lọc chất lượng + Khử trùng lặp bố cục chữ Text-Mask NMS 64x64.
        6. Phân bổ Stratified Top-K (Intro/Body/Outro) kèm Quota Rollover.
        """
        t_total_0 = time.time()
        if not os.path.exists(video_path):
            logger.error(f"Không tìm thấy video: {video_path}")
            empty_stats = {
                "decode_time_sec": 0.0,
                "dbnet_time_sec": 0.0,
                "scoring_time_sec": 0.0,
                "total_keyframe_time_sec": 0.0,
                "sampled_candidates": 0,
                "dbnet_evaluated_frames_count": 0,
                "selected_top_k_count": 0,
            }
            return ([], empty_stats) if return_stats else []

        # 1. LẤY MẪU 1 LƯỢT TUẦN TỰ (FastSinglePassSampler)
        sampled_frames, decode_stats = self.sampler.sample_video(video_path)
        if not sampled_frames:
            empty_stats = {
                "decode_time_sec": decode_stats.get("decode_time_sec", 0.0),
                "dbnet_time_sec": 0.0,
                "scoring_time_sec": 0.0,
                "total_keyframe_time_sec": round(time.time() - t_total_0, 3),
                "sampled_candidates": 0,
                "dbnet_evaluated_frames_count": 0,
                "selected_top_k_count": 0,
            }
            return ([], empty_stats) if return_stats else []

        total_frames = decode_stats.get("total_video_frames", len(sampled_frames))
        fps = decode_stats.get("fps", 30.0)

        # 2. SUY LUẬN MINI-BATCH TRÊN GPU (GPUDBNetDetector)
        t_dbnet_0 = time.time()
        raw_frames_bgr = [f.frame_bgr for f in sampled_frames]
        if hasattr(self.text_detector, "detect_batch"):
            det_results = self.text_detector.detect_batch(raw_frames_bgr, batch_size=self.dbnet_batch_size)
            raw_boxes_list = [r[0] for r in det_results]
            raw_scores_list = [r[1] for r in det_results]
        else:
            raw_boxes_list = []
            raw_scores_list = []
            for frame_bgr in raw_frames_bgr:
                boxes, scores = self.text_detector.detect(frame_bgr)
                raw_boxes_list.append(boxes)
                raw_scores_list.append(scores)
        t_dbnet = round(time.time() - t_dbnet_0, 3)

        # 3. LỌC BỎ BANNER/WATERMARK TĨNH (Persistent Box Suppression)
        t_score_0 = time.time()
        active_boxes_list, active_scores_list = suppress_persistent_boxes(
            raw_boxes_list,
            raw_scores_list,
            iou_thresh=self.persistent_box_iou_thresh,
            min_consecutive=self.persistent_min_consecutive_scenes,
        )

        # 4. CHẤM ĐIỂM TIME-AWARE SPATIAL SCORING & TÍNH MẶT NẠ 64x64
        all_candidates: List[KeyframeCandidate] = []
        for idx_pos, s_frame in enumerate(sampled_frames):
            frame_bgr = s_frame.frame_bgr
            f_idx = s_frame.frame_idx
            img_h, img_w = frame_bgr.shape[:2]
            norm_time = s_frame.norm_time
            zone = get_temporal_zone(norm_time)

            boxes = active_boxes_list[idx_pos]
            scores = active_scores_list[idx_pos]

            box_cnt_eff, avg_sc_eff, area_eff, comp_sc, t_weight, final_sc = compute_time_aware_score(
                boxes=boxes,
                scores=scores,
                img_w=img_w,
                img_h=img_h,
                norm_time=norm_time,
                enable_subtitle_suppression=self.enable_subtitle_suppression,
            )

            sharpness = s_frame.sharpness
            mask_64 = compute_text_mask_64(boxes, img_w=img_w, img_h=img_h, grid_size=64)

            pil_img = None
            time_sec = s_frame.timestamp_sec

            metrics_dict = {
                "dt_boxes": [b.tolist() if hasattr(b, "tolist") else b for b in boxes],
                "scores": scores,
                "box_count": int(round(box_cnt_eff)),
                "avg_score": round(avg_sc_eff, 4),
                "text_area_ratio": round(area_eff, 6),
                "composite_score": round(comp_sc, 4),
                "final_score": round(final_sc, 4),
                "is_subtitle_filtered": (norm_time < 0.80 and box_cnt_eff < len(raw_boxes_list[idx_pos])),
                "temporal_zone": zone,
            }

            all_candidates.append(
                KeyframeCandidate(
                    frame_idx=f_idx,
                    timestamp_sec=round(time_sec, 3),
                    norm_time=round(norm_time, 4),
                    temporal_zone=zone,
                    box_count_eff=round(box_cnt_eff, 3),
                    avg_score_eff=round(avg_sc_eff, 4),
                    area_ratio_eff=round(area_eff, 6),
                    composite_score=round(comp_sc, 4),
                    time_weight=t_weight,
                    final_score=round(final_sc, 4),
                    sharpness_score=round(sharpness, 2),
                    text_mask_64=mask_64,
                    clean_frame_pil=pil_img,
                    frame_bgr=frame_bgr if keep_frames_in_memory else None,
                    metrics=metrics_dict,
                    scene_index=idx_pos + 1,
                )
            )

        # 5. LỌC CHẤT LƯỢNG TỐI THIỂU + KHỬ TRÙNG LẶP MASK IOU + CHỌN STRATIFIED TOP-K
        qualified = [
            c for c in all_candidates
            if c.box_count_eff > 0
            and c.avg_score_eff >= self.min_avg_score
            and c.area_ratio_eff >= self.min_text_area_ratio
        ]

        deduped_qualified = deduplicate_by_text_mask_nms(qualified, mask_iou_thresh=self.text_mask_iou_thresh)

        # Fallback 1: Nếu chưa đủ K frame, bổ sung từ các frame có chữ còn lại
        if len(deduped_qualified) < top_k:
            any_text_cands = [c for c in all_candidates if c.box_count_eff > 0]
            deduped_any = deduplicate_by_text_mask_nms(any_text_cands, mask_iou_thresh=self.text_mask_iou_thresh)
            existing_ids = {c.frame_idx for c in deduped_qualified}
            for cand in deduped_any:
                if cand.frame_idx not in existing_ids:
                    deduped_qualified.append(cand)
                    existing_ids.add(cand.frame_idx)

        # Fallback 2: Nếu toàn bộ video không có chữ nào, lấy 1 frame giữa và 1 frame cuối
        if not deduped_qualified:
            mid_pos = len(all_candidates) // 2
            last_pos = len(all_candidates) - 1
            fallback_picks = [all_candidates[mid_pos]]
            if last_pos != mid_pos:
                fallback_picks.append(all_candidates[last_pos])
            result = fallback_picks[:top_k]
        elif self.enable_stratified_topk:
            result = allocate_stratified_topk(deduped_qualified, top_k=top_k)
        else:
            top_global = sorted(deduped_qualified, key=lambda c: c.final_score, reverse=True)[:top_k]
            result = sorted(top_global, key=lambda c: c.frame_idx)

        # Giải phóng bộ nhớ của các candidate không được chọn
        selected_ids = {c.frame_idx for c in result}
        for c in all_candidates:
            if c.frame_idx not in selected_ids:
                c.frame_bgr = None
                c.clean_frame_pil = None

        if keep_frames_in_memory:
            for c in result:
                if c.frame_bgr is not None and c.clean_frame_pil is None:
                    c.clean_frame_pil = Image.fromarray(cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB))

        for i, c in enumerate(result, 1):
            c.scene_index = i

        t_scoring = round(time.time() - t_score_0, 3)
        t_total = round(time.time() - t_total_0, 3)

        kf_stats = {
            "decode_time_sec": decode_stats.get("decode_time_sec", 0.0),
            "dbnet_time_sec": t_dbnet,
            "scoring_time_sec": t_scoring,
            "total_keyframe_time_sec": t_total,
            "total_video_frames": total_frames,
            "fps": fps,
            "sampled_candidates": len(sampled_frames),
            "dbnet_evaluated_frames_count": len(sampled_frames),
            "selected_top_k_count": len(result),
        }

        logger.info(
            f"select_keyframes hoàn tất: chọn {len(result)}/{top_k} frames | "
            f"Decode: {kf_stats['decode_time_sec']:.3f}s, DBNet: {t_dbnet:.3f}s, Scoring: {t_scoring:.3f}s, "
            f"Tổng: {t_total:.3f}s"
        )

        if return_stats:
            return result, kf_stats
        return result

    def export_drawn_frames(
        self,
        candidates: Union[List[KeyframeCandidate], Tuple[List[KeyframeCandidate], Any]],
        output_dir: str,
        video_id: str,
    ) -> List[str]:
        """
        Lưu ảnh có vẽ bounding box và thông tin điểm số phục vụ debug hoặc UI preview.
        """
        if isinstance(candidates, tuple) and len(candidates) >= 1 and isinstance(candidates[0], list):
            candidates = candidates[0]

        save_dir = os.path.join(output_dir, video_id)
        os.makedirs(save_dir, exist_ok=True)
        saved_paths: List[str] = []

        for rank, c in enumerate(candidates, 1):
            if c.frame_bgr is None:
                continue

            dt_boxes = c.metrics.get("dt_boxes", [])
            scores = c.metrics.get("scores", [])
            drawn = draw_detection_boxes(c.frame_bgr, dt_boxes, scores)

            info_text = (
                f"Rank #{rank} | Zone: {c.temporal_zone.upper()} | "
                f"Time: {c.middle_time_str} | Final: {c.final_score:.2f} | Sharp: {c.sharpness_score:.0f}"
            )
            cv2.putText(
                drawn,
                info_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            time_clean = c.middle_time_str.replace(":", "-").replace(".", "_")
            filename = f"rank_{rank:03d}_scene_{c.scene_index:03d}_mid_{c.middle_frame}_{time_clean}.jpg"
            save_path = os.path.join(save_dir, filename)
            cv2_imwrite(save_path, drawn)
            saved_paths.append(save_path)

        return saved_paths
