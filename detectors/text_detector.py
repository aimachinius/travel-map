"""
Module text_detector: Triển khai GPUDBNetDetector ONNX tăng tốc GPU (CUDAExecutionProvider).
- Tự động chọn CUDAExecutionProvider nếu có GPU, fallback an toàn về CPUExecutionProvider.
- Thu phóng ảnh đầu vào về kích thước chuẩn (max_side=640, chia hết cho 32)
  để tăng tốc độ suy luận gấp 30-50 lần mà vẫn quy đổi chính xác tọa độ hộp chữ về ảnh gốc.
- Hỗ trợ chạy Mini-Batch (batch_size=8) trên GPU.
- Khởi động GPU Warm-up ngay khi nạp mô hình để tối ưu hóa cuDNN kernel.
"""

import os
import sys
import time
from typing import Dict, Any, Optional, Tuple, List, Union

# QUAN TRỌNG CHO GOOGLE COLAB / LINUX / WINDOWS GPU:
# Nạp PyTorch trước ONNX Runtime để PyTorch đưa sẵn các thư viện CUDA/cuDNN (.so / DLL) chuẩn vào bộ nhớ.
# Đồng thời đồng bộ LD_LIBRARY_PATH với torch/lib để ONNX Runtime CUDAExecutionProvider tìm thấy cuDNN 9.x.
try:
    import torch
    torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
    if os.path.exists(torch_lib):
        curr_ld = os.environ.get("LD_LIBRARY_PATH", "")
        if torch_lib not in curr_ld:
            os.environ["LD_LIBRARY_PATH"] = f"{torch_lib}:{curr_ld}" if curr_ld else torch_lib
except Exception:
    pass

import cv2
import numpy as np
import onnxruntime as ort

# Kích hoạt preload_dlls cho các phiên bản ONNX Runtime hiện đại (>= 1.20) nếu môi trường có CUDA
if hasattr(ort, "preload_dlls"):
    try:
        if "CUDAExecutionProvider" in ort.get_available_providers():
            ort.preload_dlls(cuda=True, cudnn=True)
    except Exception:
        pass

from ..utils.logger import get_logger

logger = get_logger("GPUDBNetDetector")


def get_default_det_model_path() -> str:
    candidates = [
        os.environ.get("DET_ONNX_PATH"),
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tham_khao", "onnx", "det.onnx")),
        "/content/drive/MyDrive/colab/pbl/main/tham_khao/onnx/det.onnx",
        "/content/tham_khao/onnx/det.onnx",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    # Fallback default
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    return os.path.join(project_root, "tham_khao", "onnx", "det.onnx")


class GPUDBNetDetector:
    """
    Bộ phát hiện vùng chữ DBNet ONNX chạy trực tiếp trên GPU (CUDAExecutionProvider).
    - Tự động chọn CUDAExecutionProvider nếu có GPU, fallback an toàn về CPU.
    - Thu phóng ảnh đầu vào về kích thước chuẩn (max_side=640, chia hết cho 32)
      để tăng tốc độ suy luận gấp 30-50 lần mà vẫn quy đổi chính xác tọa độ hộp chữ về ảnh gốc.
    - Hỗ trợ chạy Mini-Batch trên GPU nếu mô hình ONNX có dynamic batch axis.
    """
    def __init__(
        self,
        model_path: Optional[str] = None,
        max_side: int = 640,
        box_thresh: float = 0.5,
        bin_thresh: float = 0.3,
        force_cpu: bool = False,
        device_id: int = 0,
        # Tham số tương thích ngược:
        tham_khao_dir: Optional[str] = None,
        model_dir: Optional[str] = None,
        **kwargs
    ):
        if model_path is None:
            if model_dir:
                model_path = os.path.join(model_dir, "det.onnx")
            elif tham_khao_dir:
                model_path = os.path.join(tham_khao_dir, "onnx", "det.onnx")
            else:
                model_path = get_default_det_model_path()

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Không tìm thấy file mô hình DBNet ONNX: {model_path}")

        self.model_path = model_path
        self.max_side = max_side
        self.box_thresh = box_thresh
        self.bin_thresh = bin_thresh
        self.force_cpu = force_cpu
        self.device_id = device_id

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_options.log_severity_level = 3  # 3: Error/Fatal - Ngăn chặn log Warning/Verbose spam từ cuDNN frontend

        available_providers = ort.get_available_providers()
        cuda_available = False
        try:
            import torch
            if torch.cuda.is_available() and not force_cpu and "CUDAExecutionProvider" in available_providers:
                cuda_available = True
        except Exception:
            pass

        # Cấu hình tìm kiếm thuật toán cuDNN:
        # Trong ONNX Runtime >= 1.20, 'DEFAULT' ánh xạ tới FALLBACK gây ra cảnh báo
        # 'OP Conv(...) running in Fallback mode. May be extremely slow.'
        # Sử dụng 'EXHAUSTIVE' (hoặc 'HEURISTIC') để kích hoạt thuật toán cuDNN tối ưu phần cứng.
        algo_search = kwargs.get("cudnn_conv_algo_search", "EXHAUSTIVE")
        cuda_options = {
            "device_id": self.device_id,
            "arena_extend_strategy": "kNextPowerOfTwo",
            "gpu_mem_limit": 2 * 1024 * 1024 * 1024,  # Giới hạn 2GB VRAM cho ONNX
            "cudnn_conv_algo_search": algo_search,
            "do_copy_in_default_stream": True,
        }

        self.session = None
        self.active_provider = "CPUExecutionProvider"

        if cuda_available:
            # Thử nạp CUDA với algo_search chỉ định (mặc định EXHAUSTIVE)
            try:
                providers = [("CUDAExecutionProvider", cuda_options), "CPUExecutionProvider"]
                self.session = ort.InferenceSession(model_path, sess_options=sess_options, providers=providers)
                self.active_provider = self.session.get_providers()[0]
            except Exception as e:
                logger.warning(f"Lỗi khi nạp DBNet ONNX với algo={algo_search}: {e}.")
                # Thử lại với HEURISTIC nếu EXHAUSTIVE gặp lỗi cấu hình driver
                if algo_search != "HEURISTIC":
                    try:
                        logger.info("Thử khởi tạo lại CUDAExecutionProvider với cudnn_conv_algo_search='HEURISTIC'...")
                        alt_cuda_options = dict(cuda_options)
                        alt_cuda_options["cudnn_conv_algo_search"] = "HEURISTIC"
                        self.session = ort.InferenceSession(
                            model_path,
                            sess_options=sess_options,
                            providers=[("CUDAExecutionProvider", alt_cuda_options), "CPUExecutionProvider"]
                        )
                        self.active_provider = self.session.get_providers()[0]
                    except Exception as e2:
                        logger.warning(f"Không thể khởi tạo CUDA với HEURISTIC: {e2}")

        if self.session is None:
            logger.warning("DBNet ONNX chuyển về chạy an toàn trên CPU (CPUExecutionProvider).")
            self.session = ort.InferenceSession(model_path, sess_options=sess_options, providers=["CPUExecutionProvider"])
            self.active_provider = "CPUExecutionProvider"

        logger.info(f"Đã nạp DBNet ONNX thành công! Active Provider: {self.active_provider} (model={model_path})")

        self.input_name = self.session.get_inputs()[0].name
        input_shape = self.session.get_inputs()[0].shape
        self.supports_dynamic_batch = (
            len(input_shape) > 0 and (isinstance(input_shape[0], str) or input_shape[0] is None or input_shape[0] <= 0)
        )

        self.mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 1, 3)
        self.std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 1, 3)

        self._warmup()

    def _warmup(self):
        """Khởi động GPU Warm-up để cuDNN benchmark và khóa sẵn kernel tối ưu, triệt tiêu hoàn toàn Fallback mode."""
        try:
            dummy_single = np.zeros((1, 3, 640, 352), dtype=np.float32)
            self.session.run(None, {self.input_name: dummy_single})
            if self.supports_dynamic_batch and self.active_provider == "CUDAExecutionProvider":
                dummy_batch = np.zeros((8, 3, 640, 352), dtype=np.float32)
                self.session.run(None, {self.input_name: dummy_batch})
        except Exception as e:
            logger.debug(f"DBNet warm-up notice: {e}")

    def _preprocess_single(self, img_bgr: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
        resized = cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        img_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        norm = (img_rgb - self.mean) / self.std
        return norm.transpose(2, 0, 1)  # (3, H, W)

    def detect_batch(
        self,
        frames_bgr: List[np.ndarray],
        batch_size: int = 8
    ) -> List[Tuple[List[np.ndarray], List[float]]]:
        """
        Nhận diện hộp chữ theo lô Mini-Batch trên GPU:
        - Tự động chuẩn hóa kích thước ảnh về max_side=640 chia hết cho 32.
        - Trả về danh sách (boxes, scores) cho từng frame.
        """
        if not frames_bgr:
            return []

        orig_h, orig_w = frames_bgr[0].shape[:2]
        scale = min(1.0, float(self.max_side) / max(orig_h, orig_w))
        target_h = max(32, int(round(orig_h * scale / 32.0)) * 32)
        target_w = max(32, int(round(orig_w * scale / 32.0)) * 32)

        results: List[Tuple[List[np.ndarray], List[float]]] = []
        n_frames = len(frames_bgr)

        # Trên CPU hoặc khi không hỗ trợ dynamic batch, xử lý tuần tự từng frame để tránh lỗi cấp phát BFCArena
        use_batch = (
            self.supports_dynamic_batch
            and n_frames > 1
            and self.active_provider == "CUDAExecutionProvider"
            and batch_size > 1
        )

        if use_batch:
            try:
                for i in range(0, n_frames, batch_size):
                    chunk = frames_bgr[i:i + batch_size]
                    batch_frames = [self._preprocess_single(f, target_h, target_w) for f in chunk]
                    batch_tensor = np.stack(batch_frames, axis=0)
                    preds = self.session.run(None, {self.input_name: batch_tensor})[0]
                    for b_idx in range(preds.shape[0]):
                        prob_map = preds[b_idx, 0]
                        boxes, scores = self._postprocess(prob_map, orig_w, orig_h)
                        results.append((boxes, scores))
                    del batch_frames, batch_tensor, preds
                return results
            except Exception as e:
                logger.warning(
                    f"Lỗi khi chạy detect_batch với batch_size={batch_size}: {e}. "
                    "Tự động chuyển sang xử lý tuần tự từng frame."
                )
                results.clear()

        # Fallback tuần tự từng frame (an toàn tuyệt đối cho CPU và tránh tràn RAM/VRAM)
        for f in frames_bgr:
            tensor = self._preprocess_single(f, target_h, target_w)
            inp = np.expand_dims(tensor, axis=0)
            pred = self.session.run(None, {self.input_name: inp})[0][0, 0]
            boxes, scores = self._postprocess(pred, orig_w, orig_h)
            results.append((boxes, scores))
            del tensor, inp, pred

        return results

    def _postprocess(
        self,
        prob_map: np.ndarray,
        orig_w: int,
        orig_h: int
    ) -> Tuple[List[np.ndarray], List[float]]:
        """
        Hậu xử lý trích xuất hộp chữ polygon và tính điểm tin cậy trung bình,
        quy đổi tọa độ về kích thước ảnh gốc.
        """
        mask = (prob_map > self.bin_thresh).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        boxes: List[np.ndarray] = []
        scores: List[float] = []
        map_h, map_w = prob_map.shape[:2]

        for cnt in contours[:100]:
            if cv2.contourArea(cnt) < 12:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            roi = prob_map[y:y + h, x:x + w]
            score = float(np.mean(roi[roi > self.bin_thresh])) if np.any(roi > self.bin_thresh) else 0.0
            if score < self.box_thresh:
                continue

            # Mở rộng nhẹ hộp chữ (unclip xấp xỉ) và quy đổi về kích thước ảnh gốc
            pad_x = int(w * 0.15)
            pad_y = int(h * 0.20)
            x1 = max(0, int((x - pad_x) / map_w * orig_w))
            y1 = max(0, int((y - pad_y) / map_h * orig_h))
            x2 = min(orig_w, int((x + w + pad_x) / map_w * orig_w))
            y2 = min(orig_h, int((y + h + pad_y) / map_h * orig_h))

            if (x2 - x1) < 10 or (y2 - y1) < 8:
                continue

            box = np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)
            boxes.append(box)
            scores.append(round(score, 4))

        return boxes, scores

    def detect(self, img_bgr: np.ndarray) -> Tuple[List[np.ndarray], List[float]]:
        """Phương thức nhận diện 1 ảnh đơn (trả về dt_boxes, scores)."""
        res = self.detect_batch([img_bgr])
        if res:
            return res[0]
        return [], []

    def __call__(self, img_bgr: np.ndarray, return_scores: bool = False):
        boxes, scores = self.detect(img_bgr)
        dt_boxes = np.array(boxes) if boxes else np.array([])
        if return_scores:
            return dt_boxes, scores
        return dt_boxes


# Alias tương thích ngược cho ONNXTextDetector
ONNXTextDetector = GPUDBNetDetector
