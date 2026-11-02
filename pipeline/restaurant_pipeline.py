"""
Module restaurant_pipeline: Tầng điều phối hợp nhất toàn bộ pipeline trích xuất quán ăn từ video và kịch bản.
"""

import os
import time
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import cv2
import numpy as np

from ..config.settings import PipelineConfig, default_config
from ..detectors.frame_selector import TextKeyframeSelector, FrameCandidate
from ..vlm.vintern_extractor import Vintern1BExtractor
from ..utils.io_utils import cv2_imwrite
from ..utils.logger import get_logger

logger = get_logger("RestaurantPipeline")


@dataclass
class RestaurantExtractionResult:
    """
    Kết quả trích xuất thông tin quán ăn từ một video.
    """
    video_id: str
    restaurant_name: Optional[str]
    address: Optional[str]
    nguồn_tên_quán: Optional[str] = None
    nguồn_địa_chỉ: Optional[str] = None
    log_detect: Optional[str] = None
    selected_frames_count: int = 0
    raw_vlm_output: Optional[str] = None
    execution_time_sec: float = 0.0
    status: str = "SUCCESS"  # SUCCESS, NO_FRAMES, VLM_ERROR, INVALID_VIDEO
    error_message: Optional[str] = None
    selected_frames_info: Optional[List[Dict[str, Any]]] = None
    saved_frames: Optional[List[str]] = None
    frames_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["execution_time_sec"] = round(self.execution_time_sec, 2)
        return d


class RestaurantExtractorPipeline:
    """
    Pipeline hợp nhất End-to-End:
    Video + Script -> Keyframe Selection (PySceneDetect + DBNet ONNX) -> Vintern-1B VLM -> Kết quả chuẩn.
    """
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        frame_selector: Optional[TextKeyframeSelector] = None,
        vlm_extractor: Optional[Vintern1BExtractor] = None,
        lazy_load_vlm: bool = True,
    ):
        self.config = config or default_config
        self.frame_selector = frame_selector or TextKeyframeSelector()
        self.vlm_extractor = vlm_extractor
        self.lazy_load_vlm = lazy_load_vlm

        if self.vlm_extractor is None and not self.lazy_load_vlm:
            self.init_vlm()


    def init_vlm(self):
        """
        Khởi tạo khối mô hình VLM Vintern-1B.
        """
        if self.vlm_extractor is None:
            logger.info("Đang khởi tạo Vintern1BExtractor cho pipeline...")
            self.vlm_extractor = Vintern1BExtractor(
                model_id=self.config.vlm_model_id,
                device=self.config.vlm_device,
                max_dynamic_patches=self.config.max_dynamic_patches,
                image_size=self.config.image_size,
                auto_load=True,
            )

    def _load_cached_keyframes(self, vid: str) -> Optional[List[np.ndarray]]:
        """
        Kiểm tra và tải khung hình sạch có sẵn từ thư mục selected_text_output (nếu có).
        Đảm bảo tính tương đồng tối đa với thiết kế mẫu Vintern1B_v2.ipynb.
        """
        import cv2
        project_root = self.config.project_root

        candidate_dirs = [
            os.path.join(project_root, "selected_text_output", str(vid), "selected_text_frames"),
            os.path.join(project_root, "selected_text_output", str(vid), "frames"),
            os.path.join(project_root, "selected_text_output", str(vid), "selected_text_frames_drawn"),
        ]

        valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
        for f_dir in candidate_dirs:
            if os.path.exists(f_dir):
                files = sorted([
                    os.path.join(f_dir, f) for f in os.listdir(f_dir)
                    if os.path.splitext(f.lower())[1] in valid_exts
                ])
                if files:
                    frames = []
                    for f_path in files[:self.config.top_k_frames]:
                        data = np.fromfile(f_path, dtype=np.uint8)
                        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
                        if img is not None:
                            frames.append(img)
                    if frames:
                        logger.info(f"Nạp thành công {len(frames)} keyframes sạch từ thư mục cache: {f_dir}")
                        return frames
        return None

    def process_video(
        self,
        video_path: str,
        script: str = "",
        video_id: Optional[str] = None,
    ) -> RestaurantExtractionResult:
        """
        Xử lý hoàn chỉnh 1 video review ẩm thực:
        1. Trích chọn Top-K keyframe chứa văn bản có điểm tin cậy cao nhất.
        2. Tùy chọn lưu ảnh visualization ra đĩa.
        3. Đưa các keyframe và script vào mô hình Vintern-1B để bóc tách thông tin quán ăn.
        """
        start_time = time.time()
        vid = str(video_id) if video_id else os.path.splitext(os.path.basename(video_path))[0]

        if not os.path.exists(video_path):
            return RestaurantExtractionResult(
                video_id=vid,
                restaurant_name=None,
                address=None,
                status="INVALID_VIDEO",
                error_message=f"Không tìm thấy file video: {video_path}",
                execution_time_sec=time.time() - start_time,
            )

        logger.info(f"=== [BẮT ĐẦU XỬ LÝ VIDEO: {vid}] ===")

        # 1. Trích chọn Keyframes (ưu tiên nạp từ cache selected_text_output nếu có)
        t_sel_0 = time.time()
        cached_frames = self._load_cached_keyframes(vid)
        candidates: List[FrameCandidate] = []

        if cached_frames:
            for rank, img in enumerate(cached_frames, 1):
                candidates.append(FrameCandidate(
                    scene_index=rank,
                    middle_frame=rank,
                    middle_time_sec=0.0,
                    middle_time_str="00:00:00",
                    metrics={"composite_score": 1.0, "avg_score": 1.0, "box_count": 1},
                    frame_bgr=img
                ))
            t_sel = time.time() - t_sel_0
            logger.info(f"Đã nạp {len(candidates)} keyframes từ cache trong {t_sel:.2f}s")
        else:
            select_out = self.frame_selector.select_keyframes(
                video_path=video_path,
                top_k=self.config.top_k_frames,
                sort_by=self.config.sort_by,
                min_score=self.config.min_text_score,
                min_area_ratio=self.config.min_text_area_ratio,
                keep_frames_in_memory=True,
            )
            if isinstance(select_out, tuple) and len(select_out) >= 1 and isinstance(select_out[0], list):
                candidates = select_out[0]
            else:
                candidates = select_out
            t_sel = time.time() - t_sel_0
            logger.info(f"Đã chọn {len(candidates)} keyframes trong {t_sel:.2f}s")

        if not candidates:
            return RestaurantExtractionResult(
                video_id=vid,
                restaurant_name=None,
                address=None,
                selected_frames_count=0,
                status="NO_FRAMES",
                error_message="Không tìm thấy khung hình nào chứa văn bản đạt ngưỡng tin cậy.",
                execution_time_sec=time.time() - start_time,
            )

        # 2. Lưu ảnh drawn nếu được cấu hình
        target_out_dir = self.config.default_output_dir
        if self.config.save_drawn_frames and not cached_frames:
            out_drawn_dir = self.config.drawn_output_dir or target_out_dir
            self.frame_selector.export_drawn_frames(candidates, out_drawn_dir, vid)

        # 3. Lưu các frame thực tế đưa vào VLM vào output_results/{vid}/frames/
        frames_out_dir = os.path.join(target_out_dir, vid, "frames")
        os.makedirs(frames_out_dir, exist_ok=True)
        saved_frame_paths = []

        # Chuẩn bị ảnh và thông tin tóm tắt
        frames_for_vlm = []
        frames_info = []
        for rank, c in enumerate(candidates, 1):
            if c.frame_bgr is not None:
                frames_for_vlm.append(c.frame_bgr)
                f_name = f"frame_{rank:02d}.jpg"
                f_path = os.path.join(frames_out_dir, f_name)
                cv2_imwrite(f_path, c.frame_bgr)
                saved_frame_paths.append(os.path.join("frames", f_name))

            frames_info.append({
                "rank": rank,
                "scene_index": c.scene_index,
                "middle_frame": c.middle_frame,
                "timestamp": c.middle_time_str,
                "composite_score": round(c.composite_score, 4),
                "avg_score": round(c.avg_score, 4),
                "box_count": c.box_count,
            })

        # 4. Suy luận qua Vintern-1B VLM
        if self.vlm_extractor is None:
            self.init_vlm()

        try:
            t_vlm_0 = time.time()
            vlm_res = self.vlm_extractor.extract(
                frames=frames_for_vlm,
                script=script,
                video_id=vid,
                max_new_tokens=self.config.vlm_max_new_tokens,
                temperature=self.config.vlm_temperature,
                repetition_penalty=self.config.vlm_repetition_penalty,
            )
            t_vlm = time.time() - t_vlm_0
            logger.info(f"Suy luận Vintern-1B hoàn tất trong {t_vlm:.2f}s")

            evidence = vlm_res.get("evidence", {}) or {}
            nguon_name = vlm_res.get("nguồn_tên_quán") or evidence.get("nguồn_tên_quán")
            nguon_addr = vlm_res.get("nguồn_địa_chỉ") or evidence.get("nguồn_địa_chỉ")
            log_detect = vlm_res.get("log_detect")

            result = RestaurantExtractionResult(
                video_id=vid,
                restaurant_name=vlm_res.get("tên_quán"),
                address=vlm_res.get("địa_chỉ"),
                nguồn_tên_quán=nguon_name,
                nguồn_địa_chỉ=nguon_addr,
                log_detect=log_detect,
                selected_frames_count=len(candidates),
                raw_vlm_output=vlm_res.get("raw_output"),
                execution_time_sec=time.time() - start_time,
                status="SUCCESS",
                selected_frames_info=frames_info,
                saved_frames=saved_frame_paths,
                frames_dir=os.path.join(vid, "frames"),
            )
            logger.info(
                f"===> [KẾT QUẢ {vid}]: Tên: '{result.restaurant_name}' (Nguồn: {result.nguồn_tên_quán}) | "
                f"Địa chỉ: '{result.address}' (Nguồn: {result.nguồn_địa_chỉ})"
            )
            return result

        except Exception as e:
            logger.error(f"Lỗi trong quá trình suy luận VLM cho video {vid}: {e}")
            return RestaurantExtractionResult(
                video_id=vid,
                restaurant_name=None,
                address=None,
                selected_frames_count=len(candidates),
                execution_time_sec=time.time() - start_time,
                status="VLM_ERROR",
                error_message=str(e),
                selected_frames_info=frames_info,
            )
