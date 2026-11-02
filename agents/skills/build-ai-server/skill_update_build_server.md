---
name: upgrade-keyframe-selector-v2
description: >-
  Hướng dẫn từng bước và mã nguồn chuẩn để Agent nâng cấp hệ thống chọn khung hình (Keyframe Selection) từ phiên bản cũ (chỉ dùng PySceneDetect middle_frame + DBNet глобаl Top-K) lên phiên bản v2: Lấy mẫu lai Hybrid Sampling (Scene Middle + Tail Dense Sampling 0.5s), Lọc Banner tĩnh (Persistent Box Suppression), Khử trùng lặp bố cục chữ (Text-Mask IoU 64x64), Chấm điểm Không gian phụ thuộc Thời gian (Time-Aware Spatial Scoring), và Chọn Top-K Phân tầng theo hạn ngạch (Stratified Top-K).
---

# 🛠️ SKILL: NÂNG CẤP HỆ THỐNG CHỌN KEYFRAME LÊN PHIÊN BẢN V2 (`upgrade-keyframe-selector-v2`)

Tài liệu này hướng dẫn Agent thực hiện nâng cấp trực tiếp mã nguồn của hệ thống trích xuất khung hình từ phiên bản cũ sang kiến trúc **Keyframe Selection v2** mà không làm gián đoạn luồng chạy của mô hình `DBNet ONNX` hay `Vintern-1B`.

---

## 1. TỔNG QUAN CÁC THAY ĐỔI CỐT LÕI (BẢN CŨ $\rightarrow$ BẢN MỚI V2)

| Thành phần | Hệ thống bản cũ | Hệ thống bản mới (v2) | File cần chỉnh sửa |
| :--- | :--- | :--- | :--- |
| **1. Lấy mẫu khung hình** | Chỉ dùng `PySceneDetect` cắt cảnh và lấy `middle_frame`. Dễ sót card địa chỉ ở cuối cảnh dài hoặc Outro ngắn dưới 15 frames. | **Hybrid Sampling**: Giữ `middle_frame` cho $0\% \rightarrow 80\%$ thời lượng đầu; bật **Tail Dense Sampling** lấy mẫu mỗi $0.5\text{s}$ cho $80\% \rightarrow 100\%$ cuối video. | `src/detectors/scene_detector.py` |
| **2. Lọc tiêu đề/Banner cố định** | Chấm điểm lại cùng một dòng tiêu đề gắn cố định xuyên suốt 4–5 cảnh đầu, gây trùng lặp kết quả. | **Persistent Box Suppression**: Tự động loại bỏ các hộp chữ đứng yên ($\text{Box\_IoU} \ge 0.75$ qua $\ge 3$ cảnh liên tiếp) khỏi phép tính điểm từ cảnh thứ 2. | `src/detectors/frame_selector.py` |
| **3. Khử trùng lặp bố cục chữ** | Không kiểm tra độ trùng lặp vị trí chữ giữa các frame ứng viên. | **Temporal Text-Mask NMS**: Quy đổi hộp chữ về lưới nhị phân $64 \times 64$ và gộp các frame có $\text{Mask\_IoU} \ge 0.65$ (giữ frame có điểm & độ nét cao nhất). | `src/detectors/frame_selector.py` |
| **4. Bộ lọc phụ đề & Trọng số thời gian** | Phạt cố định $0.2\times$ cho vùng dưới ($Y \in [60\%, 90\%]$) trên toàn video, vô tình phạt luôn card địa chỉ ở cuối video. | **Time-Aware Spatial Scoring**: Gỡ mức phạt vùng dưới (về $1.0\times$) khi ở $20\%$ cuối video ($t \ge 0.80$) và có cụm $\ge 2$ dòng chữ xếp dọc; nhân thêm trọng số thời gian $W_{\text{time}}(t)$. | `src/detectors/frame_selector.py` |
| **5. Quy tắc chọn Top-K** | Sắp xếp toàn cục (Global Top-K), dễ bị một phân đoạn chiếm hết suất. | **Stratified Top-K**: Chia hạn ngạch theo 3 vùng `Intro` ($0\% \rightarrow 25\%$), `Body` ($25\% \rightarrow 75\%$), `Outro` ($75\% \rightarrow 100\%$) kèm cơ chế dồn suất trống về `Outro`. | `src/detectors/frame_selector.py` |

---

## 2. QUY TRÌNH 5 BƯỚC NÂNG CẤP DÀNH CHO AGENT

### Bước 1: Cập nhật cấu hình tại `src/config/settings.py`

Bổ sung các tham số điều khiển thuật toán v2 vào class cấu hình:

~~~python
# src/config/settings.py
from dataclasses import dataclass

@dataclass
class KeyframeConfig:
    # 1. Tham số Hybrid Scene & Tail Sampling
    scene_threshold: float = 27.0
    min_scene_len: int = 15
    enable_hybrid_tail_sampling: bool = True
    tail_start_ratio: float = 0.80          # Bắt đầu lấy mẫu dày từ 80% thời lượng video
    tail_sample_interval_sec: float = 0.5   # Lấy mẫu mỗi 0.5 giây ở phần đuôi
    min_frame_gap_sec: float = 0.25         # Khoảng cách tối thiểu giữa 2 frame ứng viên

    # 2. Tham số Lọc Banner tĩnh & Khử trùng lặp Mask IoU
    persistent_box_iou_thresh: float = 0.75
    persistent_min_consecutive_scenes: int = 3
    text_mask_grid_size: int = 64
    text_mask_iou_thresh: float = 0.65

    # 3. Tham số Chất lượng tối thiểu & Stratified Top-K
    min_avg_score: float = 0.40
    min_text_area_ratio: float = 0.0005
    enable_stratified_topk: bool = True
    default_top_k: int = 4
~~~

---

### Bước 2: Nâng cấp `src/detectors/scene_detector.py` (Hybrid Sampling)

Thay thế logic chỉ lấy `middle_frame` đơn thuần bằng kết hợp `PySceneDetect` ($0\% \rightarrow 80\%$) và `Tail Dense Sampling` ($80\% \rightarrow 100\%$):

~~~python
# src/detectors/scene_detector.py
import cv2
from typing import List, Tuple
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector


class HybridSceneDetector:
    def __init__(
        self,
        threshold: float = 27.0,
        min_scene_len: int = 15,
        enable_tail_sampling: bool = True,
        tail_start_ratio: float = 0.80,
        tail_interval_sec: float = 0.5,
        min_frame_gap_sec: float = 0.25,
    ):
        self.threshold = threshold
        self.min_scene_len = min_scene_len
        self.enable_tail_sampling = enable_tail_sampling
        self.tail_start_ratio = tail_start_ratio
        self.tail_interval_sec = tail_interval_sec
        self.min_frame_gap_sec = min_frame_gap_sec

    def get_video_metadata(self, video_path: str) -> Tuple[int, float]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Không thể mở video: {video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
        cap.release()
        return total_frames, fps

    def detect_candidate_frames(self, video_path: str) -> Tuple[List[int], int, float]:
        """
        Trả về danh sách chỉ số frame ứng viên (đã sắp xếp tăng dần và khử trùng lặp sát nhau),
        cùng với (total_frames, fps).
        """
        total_frames, fps = self.get_video_metadata(video_path)
        if total_frames <= 0:
            return [], 0, fps

        tail_boundary_frame = int(total_frames * self.tail_start_ratio)
        candidate_indices: List[int] = []

        # 1. Phát hiện chuyển cảnh bằng PySceneDetect
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(
            ContentDetector(threshold=self.threshold, min_scene_len=self.min_scene_len)
        )
        try:
            video_manager.set_downscale_factor()
            video_manager.start()
            scene_manager.detect_scenes(frame_source=video_manager)
            scene_list = scene_manager.get_scene_list()
        finally:
            video_manager.release()

        if not scene_list:
            # Nếu video không có chuyển cảnh nào, lấy frame giữa của phần đầu
            candidate_indices.append(max(0, tail_boundary_frame // 2))
        else:
            for start_tc, end_tc in scene_list:
                s_idx = start_tc.get_frames()
                e_idx = end_tc.get_frames()
                mid_idx = (s_idx + e_idx) // 2
                if not self.enable_tail_sampling or mid_idx < tail_boundary_frame:
                    candidate_indices.append(mid_idx)

        # 2. Lấy mẫu dày ở 20% cuối video (Tail Dense Sampling)
        if self.enable_tail_sampling:
            step_frames = max(1, int(round(self.tail_interval_sec * fps)))
            for f_idx in range(tail_boundary_frame, total_frames, step_frames):
                candidate_indices.append(f_idx)
            # Luôn đảm bảo có 1 frame sát cuối video (cách frame cuối ~5 frames để tránh màn hình đen)
            last_valid_idx = max(tail_boundary_frame, total_frames - 5)
            candidate_indices.append(last_valid_idx)

        # 3. Sắp xếp và gộp các frame quá sát nhau (< min_frame_gap_sec)
        candidate_indices = sorted(set(i for i in candidate_indices if 0 <= i < total_frames))
        min_gap_frames = max(1, int(round(self.min_frame_gap_sec * fps)))

        deduped_indices: List[int] = []
        for idx in candidate_indices:
            if not deduped_indices or (idx - deduped_indices[-1]) >= min_gap_frames:
                deduped_indices.append(idx)

        return deduped_indices, total_frames, fps
~~~

---

### Bước 3: Nâng cấp `src/detectors/frame_selector.py` (Core Keyframe Selector v2)

Cập nhật toàn bộ thuật toán lọc Banner tĩnh, tính `Text-Mask IoU`, chấm điểm `Time-Aware Spatial Scoring` và chọn `Stratified Top-K`:

~~~python
# src/detectors/frame_selector.py
import math
import cv2
import numpy as np
from PIL import Image
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class KeyframeCandidate:
    frame_idx: int
    timestamp_sec: float
    norm_time: float                # Vị trí thời gian chuẩn hóa t in [0.0, 1.0]
    temporal_zone: str              # "intro" | "body" | "outro"
    box_count_eff: float
    avg_score_eff: float
    area_ratio_eff: float
    composite_score: float
    time_weight: float
    final_score: float
    sharpness_score: float
    text_mask_64: np.ndarray        # Mặt nạ chữ nhị phân 64x64
    clean_frame_pil: Optional[Image.Image] = None


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
) -> Tuple[List[List[np.ndarray]], List[List[float]]]:
    """
    Loại bỏ các hộp chữ tĩnh (Static Banner / Watermark) xuất hiện lặp lại ở cùng tọa độ
    (IoU >= iou_thresh) xuyên suốt từ `min_consecutive` frame liên tiếp trở lên.
    Giữ lại ở lần xuất hiện đầu tiên, loại bỏ khỏi phép tính điểm từ frame thứ 2 của chuỗi.
    """
    n_frames = len(all_frames_boxes)
    if all_frames_scores is None:
        all_frames_scores = [[1.0] * len(boxes) for boxes in all_frames_boxes]

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
        f_scores = [s for idx, s in enumerate(all_frames_scores[t]) if not suppress_flags[t][idx]]
        filtered_boxes.append(f_boxes)
        filtered_scores.append(f_scores)

    return filtered_boxes, filtered_scores


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
~~~

---

### Bước 4: Cập nhật `TextKeyframeSelector.select_keyframes` trong `src/detectors/frame_selector.py`

Kết nối toàn bộ chuỗi xử lý từ `HybridSceneDetector` $\rightarrow$ `DBNet ONNX` $\rightarrow$ `suppress_persistent_boxes` $\rightarrow$ `compute_time_aware_score` $\rightarrow$ `deduplicate_by_text_mask_nms` $\rightarrow$ `allocate_stratified_topk`:

~~~python
class TextKeyframeSelector:
    def __init__(
        self,
        text_detector,
        scene_detector: Optional[HybridSceneDetector] = None,
        enable_subtitle_suppression: bool = True,
        persistent_box_iou_thresh: float = 0.75,
        persistent_min_consecutive_scenes: int = 3,
        text_mask_iou_thresh: float = 0.65,
        min_avg_score: float = 0.40,
        min_text_area_ratio: float = 0.0005,
        enable_stratified_topk: bool = True,
    ):
        self.text_detector = text_detector
        self.scene_detector = scene_detector or HybridSceneDetector()
        self.enable_subtitle_suppression = enable_subtitle_suppression
        self.persistent_box_iou_thresh = persistent_box_iou_thresh
        self.persistent_min_consecutive_scenes = persistent_min_consecutive_scenes
        self.text_mask_iou_thresh = text_mask_iou_thresh
        self.min_avg_score = min_avg_score
        self.min_text_area_ratio = min_text_area_ratio
        self.enable_stratified_topk = enable_stratified_topk

    def select_keyframes(
        self,
        video_path: str,
        top_k: int = 4,
        keep_frames_in_memory: bool = True,
    ) -> List[KeyframeCandidate]:
        frame_indices, total_frames, fps = self.scene_detector.detect_candidate_frames(video_path)
        if not frame_indices or total_frames <= 0:
            return []

        cap = cv2.VideoCapture(video_path)
        raw_frames_bgr: List[np.ndarray] = []
        valid_indices: List[int] = []
        raw_boxes_list: List[List[np.ndarray]] = []
        raw_scores_list: List[List[float]] = []

        try:
            for f_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                ret, frame_bgr = cap.read()
                if not ret or frame_bgr is None:
                    continue
                dt_boxes, scores = self.text_detector.detect(frame_bgr)
                raw_frames_bgr.append(frame_bgr)
                valid_indices.append(f_idx)
                raw_boxes_list.append(dt_boxes)
                raw_scores_list.append(scores)
        finally:
            cap.release()

        if not valid_indices:
            return []

        # Bước 2.1: Lọc bỏ Banner/Watermark tĩnh lặp lại qua >= 3 cảnh liên tiếp
        active_boxes_list, active_scores_list = suppress_persistent_boxes(
            raw_boxes_list,
            raw_scores_list,
            iou_thresh=self.persistent_box_iou_thresh,
            min_consecutive=self.persistent_min_consecutive_scenes,
        )

        # Bước 2.2 & Bước 3: Tính mặt nạ 64x64 và chấm điểm Time-Aware Spatial Score
        all_candidates: List[KeyframeCandidate] = []
        for idx_pos, f_idx in enumerate(valid_indices):
            frame_bgr = raw_frames_bgr[idx_pos]
            img_h, img_w = frame_bgr.shape[:2]
            norm_time = float(f_idx) / float(max(1, total_frames - 1))
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

            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            mask_64 = compute_text_mask_64(boxes, img_w=img_w, img_h=img_h, grid_size=64)

            pil_img = None
            if keep_frames_in_memory:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame_rgb)

            all_candidates.append(
                KeyframeCandidate(
                    frame_idx=f_idx,
                    timestamp_sec=round(f_idx / fps, 2),
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
                )
            )

        # Bước 4: Lọc chất lượng tối thiểu + Khử trùng lặp Mask IoU + Chọn Stratified Top-K
        qualified = [
            c for c in all_candidates
            if c.box_count_eff > 0
            and c.avg_score_eff >= self.min_avg_score
            and c.area_ratio_eff >= self.min_text_area_ratio
        ]

        deduped_qualified = deduplicate_by_text_mask_nms(qualified, mask_iou_thresh=self.text_mask_iou_thresh)

        # Fallback 1: Nếu chưa đủ K frame, bổ sung từ các frame có chữ còn lại (đã khử trùng lặp)
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
            fallback_ picks = [all_candidates[mid_pos]]
            if last_pos != mid_pos:
                fallback_picks.append(all_candidates[last_pos])
            return fallback_picks[:top_k]

        if self.enable_stratified_topk:
            return allocate_stratified_topk(deduped_qualified, top_k=top_k)

        top_global = sorted(deduped_qualified, key=lambda c: c.final_score, reverse=True)[:top_k]
        return sorted(top_global, key=lambda c: c.frame_idx)
~~~

---

### Bước 5: Kiểm thử xác thực sau khi nâng cấp (`tests/test_vision_detector.py`)

Sau khi Agent cập nhật xong các file trên, chạy lệnh kiểm thử để xác nhận tất cả các điều kiện kỹ thuật đều đạt chuẩn:

~~~bash
python -m unittest tests/test_vision_detector.py -v
~~~

Danh sách các bài kiểm thử bắt buộc phải `PASS`:
1. `test_text_mask_iou_deduplication`: Hai frame có bố cục chữ tương đương đạt $\text{Mask\_IoU} \ge 0.65$ và được gộp thành 1 frame duy nhất.
2. `test_persistent_banner_suppression`: Hộp chữ tiêu đề tĩnh lặp lại qua $\ge 3$ cảnh liên tiếp chỉ được tính điểm ở cảnh đầu và bị loại khỏi phép tính điểm từ cảnh thứ 2.
3. `test_time_aware_tail_unpenalized`: Cụm $\ge 2$ dòng chữ đặt ở nửa dưới màn hình ($Y \in [0.60, 0.90]$) tại thời điểm $t \ge 0.80$ không bị phạt $0.2\times$ và được nhân hệ số $W_{\text{time}} = 1.5\times$.
4. `test_stratified_topk_and_rollover`: Phân bổ đúng hạn ngạch `Intro` / `Body` / `Outro` và tự động dồn suất trống về `Outro` khi vùng `Body` không có ứng viên đạt chuẩn.