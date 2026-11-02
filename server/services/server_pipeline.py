"""
Module server_pipeline: Pipeline điều phối tổng thể cho AI Server v3.0 (Pure Vision & Tăng tốc GPU).
Loại bỏ hoàn toàn nhánh Speech-to-Text (PhoWhisper-medium).
Quy trình thực thi:
1. VideoDownloader: Tải video từ URL TikTok / YouTube Shorts.
2. GPUKeyframeSelector: FastSinglePassSampler (0.75s thân, 0.35s đuôi + 64x64 diff)
   + GPUDBNetDetector (CUDAExecutionProvider + max_side=640) + Stratified Top-K.
3. Vintern-1B Pure Vision: Quét OCR tuần tự trên Clean Frames + Bầu chọn Majority Voting & Fast-Path.
4. StorageManager: Lưu Cache và xuất kết quả phản hồi chuẩn hóa v3.0.
"""

import os
import time
import threading
from typing import Dict, Any, Optional, List, Callable
import cv2
import numpy as np
from PIL import Image
import torch

from ...config.settings import ServerConfig, default_server_config
from .downloader import VideoDownloader
from .storage_manager import StorageManager
from ...detectors.frame_selector import TextKeyframeSelector, KeyframeCandidate, FrameCandidate
from ...vlm.vintern_extractor import Vintern1BExtractor
from ...utils.logger import get_logger

logger = get_logger("ServerExtractionPipeline")


class ServerExtractionPipeline:
    """
    Pipeline hợp nhất End-to-End cho AI Server v3.0 (Pure Vision):
    - FastSinglePassSampler + GPUDBNetDetector (chọn Keyframe trên GPU chỉ ~1.5s - 3s).
    - Sequential Clean Frame OCR & Majority Voting với Fast-Path (Vintern-1B).
    """
    def __init__(
        self,
        config: Optional[ServerConfig] = None,
        downloader: Optional[VideoDownloader] = None,
        frame_selector: Optional[TextKeyframeSelector] = None,
        vlm_extractor: Optional[Vintern1BExtractor] = None,
        storage_manager: Optional[StorageManager] = None,
        gpu_lock_sync: Optional[threading.Lock] = None,
        lazy_load_models: bool = True,
        **kwargs
    ):
        self.config = config or default_server_config
        self.gpu_lock_sync = gpu_lock_sync or threading.Lock()
        self.downloader = downloader or VideoDownloader(self.config.videos_dir)
        self.storage_manager = storage_manager or StorageManager(self.config.storage_dir)

        # Bộ chọn Keyframe v3 chạy trực tiếp trên GPU
        kf_cfg = self.config.pipeline_config.keyframe_config
        self.frame_selector = frame_selector or TextKeyframeSelector(
            det_model_path=self.config.dbnet_onnx_path,
            use_gpu=True,
            dbnet_max_side=kf_cfg.dbnet_max_side,
            dbnet_batch_size=kf_cfg.dbnet_batch_size,
            body_sample_interval_sec=kf_cfg.body_sample_interval_sec,
            tail_sample_interval_sec=kf_cfg.tail_sample_interval_sec,
            tail_start_ratio=kf_cfg.tail_start_ratio,
            visual_diff_thresh=kf_cfg.visual_diff_thresh,
            persistent_box_iou_thresh=kf_cfg.persistent_box_iou_thresh,
            persistent_min_consecutive_scenes=kf_cfg.persistent_min_consecutive_scenes,
            text_mask_iou_thresh=kf_cfg.text_mask_iou_thresh,
            enable_stratified_topk=kf_cfg.enable_stratified_topk,
        )

        self.vlm_extractor = vlm_extractor
        if not lazy_load_models and self.vlm_extractor is None:
            self.init_vlm()

    def init_vlm(self):
        """Khởi tạo mô hình Vintern-1B VLM."""
        if self.vlm_extractor is None:
            logger.info("Đang khởi tạo Vintern1BExtractor cho Server Pipeline...")
            self.vlm_extractor = Vintern1BExtractor(
                model_id=self.config.vlm_model_id,
                device=self.config.pipeline_config.vlm_device,
                max_dynamic_patches=self.config.pipeline_config.max_dynamic_patches,
                image_size=self.config.pipeline_config.image_size,
                auto_load=True,
            )

    def process_url(
        self,
        url: str,
        top_k: int = 5,
        force_reload: bool = False,
        keep_raw_video: Optional[bool] = None,
        status_callback: Optional[Callable[[str, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Xử lý hoàn chỉnh 1 URL video review ẩm thực từ TikTok hoặc YouTube Shorts:
        1. Kiểm tra cache JSON.
        2. Tải video ngắn về đĩa (VideoDownloader).
        3. Chọn Keyframe tăng tốc GPU (FastSinglePassSampler + GPUDBNetDetector).
        4. Xóa file MP4 gốc nếu không yêu cầu lưu trữ (tiết kiệm đĩa cứng).
        5. Suy luận qua mô hình Vintern-1B Pure Vision (OCR từng frame + Majority Voting + Fast-Path).
        6. Lưu cache và đóng gói kết quả phản hồi chuẩn hóa v3.0.
        """
        start_total = time.time()
        should_keep_raw = (
            keep_raw_video if keep_raw_video is not None else self.config.keep_raw_video
        )

        def report(stage: str, pct: int):
            if status_callback:
                try:
                    status_callback(stage, pct)
                except Exception:
                    pass

        # 1. Kiểm tra Cache
        if not force_reload:
            cached = self.storage_manager.get_cached_result(url)
            if cached:
                report("Hoàn thành (Từ Cache)", 100)
                return cached

        # 2. Tải Video
        report("Đang tải video", 15)
        t_dl_0 = time.time()
        download_res = self.downloader.download_video(url, force_reload=force_reload)
        t_download = round(time.time() - t_dl_0, 2)

        if download_res.get("status") == "FAILED":
            err_resp = {
                "success": False,
                "status": "DOWNLOAD_FAILED",
                "data": None,
                "error_message": download_res.get("error_message", "Không thể tải video từ URL chỉ định."),
            }
            report("Tải video thất bại", 100)
            return err_resp

        video_path = download_res["file_path"]
        vid = download_res["video_id"]

        try:
            # 3. CHỌN KEYFRAME TĂNG TỐC GPU
            report("Đang trích chọn keyframe trên GPU", 40)
            t_kf_0 = time.time()
            with self.gpu_lock_sync:
                select_out = self.frame_selector.select_keyframes(
                    video_path=video_path,
                    top_k=top_k,
                    keep_frames_in_memory=True
                )
                if isinstance(select_out, tuple):
                    candidates, kf_stats = select_out
                else:
                    candidates = select_out
                    kf_stats = getattr(candidates, "stats", {})
            t_kf = round(time.time() - t_kf_0, 2)

            # 4. Trích xuất Clean Frames và lưu Keyframes
            clean_frames: List[Image.Image] = []
            for c in candidates:
                if c.clean_frame_pil is not None:
                    clean_frames.append(c.clean_frame_pil)
                elif c.frame_bgr is not None:
                    rgb = cv2.cvtColor(c.frame_bgr, cv2.COLOR_BGR2RGB)
                    clean_frames.append(Image.fromarray(rgb))

            clean_frame_urls = self.storage_manager.save_clean_keyframes(vid, clean_frames)

            # Lưu ảnh preview keyframe vẽ đè (để phục vụ debug / audit)
            if candidates:
                try:
                    self.frame_selector.export_drawn_frames(
                        candidates, self.config.keyframes_dir, vid
                    )
                except Exception as e:
                    logger.warning(f"Không thể xuất ảnh drawn frames: {e}")

            # Xóa file MP4 gốc ngay sau khi trích xuất keyframes
            if not should_keep_raw and os.path.exists(video_path):
                self.storage_manager.safe_remove_file(video_path)

            # 5. SUY LUẬN VINTERN-1B PURE VISION
            report("Đang phân tích OCR và kết luận với Vintern-1B", 70)
            if self.vlm_extractor is None:
                self.init_vlm()

            t_vlm_0 = time.time()
            with self.gpu_lock_sync:
                try:
                    if hasattr(self.vlm_extractor, "analyze_frames"):
                        vlm_res = self.vlm_extractor.analyze_frames(
                            frames=clean_frames,
                            candidates_meta=candidates,
                            video_id=vid
                        )
                    else:
                        vlm_res = self.vlm_extractor.analyze_video(
                            frames=clean_frames,
                            video_id=vid
                        )
                finally:
                    if hasattr(self.vlm_extractor, "clear_context"):
                        self.vlm_extractor.clear_context()
            t_vlm = round(time.time() - t_vlm_0, 2)

            # 6. Đóng gói kết quả chuẩn hóa
            report("Đang hoàn thiện phản hồi", 95)
            metrics_dict = {
                "download_time_sec": t_download,
                "keyframe_total_time_sec": t_kf,
                "video_decode_sampling_time_sec": kf_stats.get("decode_time_sec", 0.0),
                "dbnet_gpu_inference_time_sec": kf_stats.get("dbnet_time_sec", 0.0),
                "scoring_and_nms_time_sec": kf_stats.get("scoring_time_sec", 0.0),
                "vlm_sequential_inference_time_sec": t_vlm,
                "total_time_sec": round(time.time() - start_total, 2),
                "sampled_frames_count": kf_stats.get("sampled_candidates", len(clean_frames)),
                "dbnet_evaluated_frames_count": kf_stats.get("dbnet_evaluated_frames_count", len(clean_frames)),
                "selected_top_k_count": len(clean_frames),
                # Tương thích ngược:
                "stt_time_sec": 0.0,
                "keyframe_selection_time_sec": t_kf,
                "parallel_stt_and_keyframe_time_sec": t_kf,
                "stt_branch_time_sec": 0.0,
                "keyframe_branch_time_sec": t_kf,
                "vlm_inference_time_sec": t_vlm,
            }

            final_res = self._build_response(
                download_res=download_res,
                candidates=candidates,
                saved_frame_urls=clean_frame_urls,
                vlm_res=vlm_res,
                metrics=metrics_dict
            )

            self.storage_manager.save_cache_result(url, final_res)
            report("Hoàn tất", 100)
            return final_res

        except Exception as e:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.error(f"Lỗi trong quá trình xử lý pipeline: {e}")
            raise e

    def _build_response(
        self,
        download_res: Dict[str, Any],
        candidates: List[Any],
        saved_frame_urls: List[str],
        vlm_res: Dict[str, Any],
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        vid = download_res.get("video_id", "unknown")
        duration = float(download_res.get("duration", 0.0))
        file_size = float(download_res.get("file_size_mb", 0.0))
        source_url = download_res.get("source_url", "")
        platform = download_res.get("platform", "unknown")

        evidence = vlm_res.get("evidence", {})
        if not evidence and "dẫn_chứng" in vlm_res:
            evidence = vlm_res["dẫn_chứng"]

        name_src = evidence.get("name_source") or evidence.get("nguồn_tên_quán")
        addr_src = evidence.get("address_source") or evidence.get("nguồn_địa_chỉ")

        frames_ocr_details = []
        vlm_frame_details = vlm_res.get("chi_tiết_frames", [])
        for idx, c in enumerate(candidates):
            v_detail = vlm_frame_details[idx] if idx < len(vlm_frame_details) else {}
            img_url = saved_frame_urls[idx] if idx < len(saved_frame_urls) else f"/api/v1/keyframes/{vid}/frame_{idx:02d}.jpg"
            ocr_name = v_detail.get("ocr_name") or v_detail.get("tên_quán_ocr")
            ocr_addr = v_detail.get("ocr_address") or v_detail.get("địa_chỉ_ocr")
            ocr_other = v_detail.get("ocr_other") or v_detail.get("chữ_khác_ocr")

            frames_ocr_details.append({
                "frame_idx": getattr(c, "frame_idx", idx),
                "temporal_zone": getattr(c, "temporal_zone", "body"),
                "timestamp_sec": getattr(c, "timestamp_sec", 0.0),
                "final_score": getattr(c, "final_score", 0.0),
                "image_url": img_url,
                "ocr_name": ocr_name,
                "ocr_address": ocr_addr,
                "ocr_other": ocr_other,
            })

        return {
            "success": True,
            "status": "SUCCESS",
            "data": {
                "restaurant": {
                    "name": vlm_res.get("tên_quán"),
                    "address": vlm_res.get("địa_chỉ"),
                    "confidence_status": vlm_res.get("confidence_status") or vlm_res.get("độ_tin_cậy", "Cao"),
                    "evidence": {
                        "name_source": name_src,
                        "address_source": addr_src,
                    },
                    "evidence_sources": [s for s in [name_src, addr_src] if s],
                },
                "frames_ocr_details": frames_ocr_details,
                "video": {
                    "video_id": vid,
                    "platform": platform,
                    "source_url": source_url,
                    "duration_seconds": duration,
                    "file_size_mb": file_size,
                    "download_url": f"/api/v1/videos/{vid}.mp4" if os.path.exists(download_res.get("file_path", "")) else None,
                },
                "execution_metrics": metrics,
            },
            "error_message": None
        }
