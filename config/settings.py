"""
Module settings: Quản lý cấu hình tập trung cho toàn bộ hệ thống pipeline.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

# Thư mục gốc của project (cha của src/)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))


def get_default_videos_dir() -> str:
    """
    Tự động nhận diện thư mục videos tương thích cả trên Windows ('マイドライブ') và Google Colab ('/content/drive/MyDrive').
    """
    rel_path = os.path.abspath(os.path.join(PROJECT_ROOT, "..", "..", "PBL_Build_Data", "videos"))
    candidates = [
        os.environ.get("VIDEOS_DIR"),
        rel_path,
        "/content/drive/MyDrive/colab/PBL_Build_Data/videos",
        r"G:\マイドライブ\colab\PBL_Build_Data\videos",
    ]
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return rel_path if os.name != "nt" else r"G:\マイドライブ\colab\PBL_Build_Data\videos"


def is_low_vram_environment() -> bool:
    """
    Tự động phát hiện nếu GPU có VRAM < 10GB (như RTX 3070 8GB, RTX 4060 8GB) để kích hoạt Low-VRAM Mode.
    """
    try:
        import torch
        if torch.cuda.is_available():
            total_mem = torch.cuda.get_device_properties(0).total_memory
            return total_mem < 10 * 1024 * 1024 * 1024
    except Exception:
        pass
    return False


@dataclass
class KeyframeConfig:
    """
    Cấu hình chuyên biệt cho thuật toán Keyframe Selection v3 (FastSinglePassSampler + GPUDBNet):
    - FastSinglePassSampler (0-80% Stride 0.75s + 80-100% Tail 0.35s + 64x64 Visual Diff Filter)
    - GPUDBNetDetector (CUDAExecutionProvider + max_side=640 + Mini-Batch)
    - Persistent Box Suppression (IoU >= 0.75, len >= 3)
    - Temporal Text-Mask NMS (64x64, IoU >= 0.65)
    - Time-Aware Spatial Scoring & Stratified Top-K
    """
    # 1. Tham số FastSinglePassSampler (Single-Pass Sequential Grab)
    body_sample_interval_sec: float = 0.75
    tail_sample_interval_sec: float = 0.35
    tail_start_ratio: float = 0.80
    visual_diff_thresh: float = 4.5
    max_force_interval_sec: float = 2.5

    # Tương thích ngược
    scene_threshold: float = 27.0
    min_scene_len: int = 15
    enable_hybrid_tail_sampling: bool = True
    tail_interval_sec: float = 0.35
    min_frame_gap_sec: float = 0.25

    # 2. Tham số GPU DBNet Detector
    dbnet_max_side: int = 640
    dbnet_batch_size: int = 8
    dbnet_use_gpu: bool = True
    dbnet_box_thresh: float = 0.5
    dbnet_bin_thresh: float = 0.3

    # 3. Tham số Lọc Banner tĩnh & Khử trùng lặp Mask IoU
    persistent_box_iou_thresh: float = 0.75
    persistent_min_consecutive_scenes: int = 3
    text_mask_grid_size: int = 64
    text_mask_iou_thresh: float = 0.65

    # 4. Tham số Chất lượng tối thiểu & Stratified Top-K
    min_avg_score: float = 0.40
    min_text_area_ratio: float = 0.0005
    enable_stratified_topk: bool = True
    default_top_k: int = 5


@dataclass
class PipelineConfig:
    # 1. Đường dẫn thư mục & tài nguyên
    project_root: str = PROJECT_ROOT
    tham_khao_dir: str = field(default_factory=lambda: os.path.join(PROJECT_ROOT, "tham_khao"))
    onnx_model_dir: str = field(default_factory=lambda: os.path.join(PROJECT_ROOT, "tham_khao", "onnx"))
    default_videos_dir: str = field(default_factory=get_default_videos_dir)
    default_csv_path: str = field(default_factory=lambda: os.path.join(PROJECT_ROOT, "video_speech_to_text.csv"))
    default_output_dir: str = field(default_factory=lambda: os.path.join(PROJECT_ROOT, "output_results"))

    # Cấu hình Keyframe Selection v3
    keyframe_config: KeyframeConfig = field(default_factory=KeyframeConfig)

    # 2. Cấu hình PySceneDetect (tương thích)
    scene_detector_type: str = "fast_single_pass"
    scene_threshold: float = 27.0
    min_scene_len: int = 15

    # 3. Cấu hình Trích chọn Text Keyframes (DBNet ONNX)
    top_k_frames: int = 5
    sort_by: str = "composite"  # "composite", "area_ratio", "avg_score", "box_count"
    min_text_score: float = 0.4
    min_text_area_ratio: float = 0.0005
    save_drawn_frames: bool = True  # Lưu ảnh có vẽ bounding box để audit
    drawn_output_dir: Optional[str] = None

    # Bộ lọc khử phụ đề TikTok (Caption Suppression)
    enable_subtitle_suppression: bool = True
    subtitle_y_min: float = 0.60
    subtitle_y_max: float = 0.90
    subtitle_x_min: float = 0.15
    subtitle_x_max: float = 0.85
    subtitle_penalty_weight: float = 0.2
    signboard_boost_weight: float = 1.5

    # 4. Cấu hình Multimodal VLM (Vintern-1B Pure Vision v3)
    vlm_model_id: str = "5CD-AI/Vintern-1B-v3_5"
    max_dynamic_patches: int = 3
    image_size: int = 448
    use_thumbnail: bool = True
    vlm_max_new_tokens: int = 256
    vlm_temperature: float = 0.1
    vlm_repetition_penalty: float = 1.05
    vlm_device: Optional[str] = None  # None: tự nhận diện 'cuda' hoặc 'cpu'

    # 5. Cấu hình Batch Processing
    skip_existing: bool = True
    verbose: bool = True
    batch_save_interval: int = 10


@dataclass
class ServerConfig:
    """
    Cấu hình chuyên biệt cho AI Server độc lập v3.0 (Pure Vision & GPU Keyframe).
    """
    host: str = "0.0.0.0"
    port: int = 8000
    vlm_model_id: str = "5CD-AI/Vintern-1B-v3_5"
    dbnet_onnx_path: str = field(
        default_factory=lambda: os.path.join(PROJECT_ROOT, "tham_khao", "onnx", "det.onnx")
    )
    
    # Quản trị tài nguyên phần cứng & VRAM
    low_vram_mode: bool = field(default_factory=is_low_vram_environment)
    max_sync_waiters: int = 2
    sync_timeout_seconds: float = 40.0
    
    # Quản lý lưu trữ & TTL
    storage_dir: str = field(default_factory=lambda: os.path.join(PROJECT_ROOT, "storage"))
    keep_raw_video: bool = False
    ttl_hours: int = 24
    max_storage_mb: int = 5000
    
    # Cầu nối mạng (Tunnel)
    tunnel_provider: str = "cloudflare"  # "cloudflare", "ngrok", "none"
    ngrok_authtoken: Optional[str] = field(default_factory=lambda: os.environ.get("NGROK_AUTHTOKEN"))
    ngrok_domain: Optional[str] = field(default_factory=lambda: os.environ.get("NGROK_DOMAIN"))

    # Pipeline con
    pipeline_config: PipelineConfig = field(default_factory=PipelineConfig)

    def __post_init__(self):
        # Tự động đồng bộ các thư mục con trong storage
        self.videos_dir = os.path.join(self.storage_dir, "videos")
        self.keyframes_dir = os.path.join(self.storage_dir, "keyframes")
        self.cache_dir = os.path.join(self.storage_dir, "cache")
        os.makedirs(self.videos_dir, exist_ok=True)
        os.makedirs(self.keyframes_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        # Áp dụng Low-VRAM Mode nếu phát hiện card đồ họa <= 8GB
        if self.low_vram_mode:
            self.pipeline_config.max_dynamic_patches = 2


default_config = PipelineConfig()
default_server_config = ServerConfig()

