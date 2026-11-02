"""
Module response: Pydantic schemas cho dữ liệu phản hồi của các endpoint API v3.0 (Pure Vision).
Tham chiếu: build_server.md (Mục 2.2).
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class RestaurantData(BaseModel):
    name: Optional[str] = Field(None, description="Tên quán ăn được bóc tách")
    address: Optional[str] = Field(None, description="Địa chỉ cụ thể của quán ăn")
    confidence_status: str = Field("Cao", description="Mức độ tin cậy: Cao, Trung bình, Thấp, UNKNOWN")
    evidence: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Nguồn dữ liệu xác thực: name_source, address_source"
    )
    evidence_sources: List[str] = Field(default_factory=list, description="[Tương thích ngược] Nguồn dữ liệu")


class VideoMetadata(BaseModel):
    video_id: str = Field(..., description="Định danh video")
    platform: str = Field("unknown", description="Nền tảng: tiktok, youtube, unknown")
    source_url: str = Field(..., description="Đường dẫn gốc")
    duration_seconds: float = Field(0.0, description="Thời lượng video (giây)")
    file_size_mb: float = Field(0.0, description="Kích thước file (MB)")
    download_url: Optional[str] = Field(None, description="Đường dẫn xem/tải lại video trên server")


class TranscriptData(BaseModel):
    """[Deprecated] Dành cho tương thích ngược nếu cần hiển thị."""
    text: str = Field("", description="Văn bản phiên âm từ giọng nói")
    status: str = Field("SKIPPED_PURE_VISION", description="Trạng thái phiên âm")
    duration_seconds: float = Field(0.0, description="Thời lượng âm thanh (giây)")


class KeyframeData(BaseModel):
    rank: int = Field(..., description="Thứ hạng điểm số")
    scene_index: int = Field(..., description="Chỉ số phân cảnh")
    middle_frame: int = Field(..., description="Vị trí frame")
    timestamp: str = Field(..., description="Mốc thời gian hiển thị")
    composite_score: float = Field(..., description="Điểm mật độ chữ và độ tin cậy")
    is_subtitle_filtered: bool = Field(False, description="Đã áp dụng bộ lọc khử phụ đề TikTok")
    preview_url: str = Field(..., description="Đường dẫn xem ảnh preview")


class KeyframeOCRDetail(BaseModel):
    frame_idx: int = Field(..., description="Chỉ số thứ tự frame")
    temporal_zone: str = Field("body", description="Phân vùng thời gian: intro, body, outro")
    timestamp_sec: float = Field(0.0, description="Mốc thời gian giây trong video")
    final_score: float = Field(0.0, description="Điểm tổng hợp Time-Aware")
    image_url: Optional[str] = Field(None, description="Đường dẫn xem clean frame")
    ocr_name: Optional[str] = Field(None, description="Tên quán trích xuất từ frame")
    ocr_address: Optional[str] = Field(None, description="Địa chỉ trích xuất từ frame")
    ocr_other: Optional[str] = Field(None, description="Chữ khác trên ảnh")


class ExecutionMetrics(BaseModel):
    download_time_sec: float = Field(0.0)
    keyframe_total_time_sec: float = Field(0.0)
    video_decode_sampling_time_sec: float = Field(0.0)
    dbnet_gpu_inference_time_sec: float = Field(0.0)
    scoring_and_nms_time_sec: float = Field(0.0)
    vlm_sequential_inference_time_sec: float = Field(0.0)
    total_time_sec: float = Field(0.0)
    sampled_frames_count: int = Field(0)
    dbnet_evaluated_frames_count: int = Field(0)
    selected_top_k_count: int = Field(0)

    # Các trường tương thích ngược:
    stt_time_sec: float = Field(0.0)
    keyframe_selection_time_sec: float = Field(0.0)
    parallel_stt_and_keyframe_time_sec: float = Field(0.0)
    stt_branch_time_sec: float = Field(0.0)
    keyframe_branch_time_sec: float = Field(0.0)
    vlm_inference_time_sec: float = Field(0.0)


class ExtractionData(BaseModel):
    restaurant: RestaurantData
    frames_ocr_details: List[KeyframeOCRDetail] = Field(default_factory=list, description="Chi tiết OCR từng frame từ Vintern-1B v3")
    video: VideoMetadata
    execution_metrics: ExecutionMetrics
    transcript: Optional[TranscriptData] = None
    keyframes: List[KeyframeData] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    success: bool = Field(..., description="Trạng thái thực thi")
    status: str = Field("SUCCESS", description="Mã trạng thái kết quả")
    data: Optional[ExtractionData] = Field(None, description="Dữ liệu kết quả chi tiết")
    error_message: Optional[str] = Field(None, description="Thông báo lỗi nếu có")


class JobCreateResponse(BaseModel):
    job_id: str = Field(..., description="Mã định danh công việc")
    status: str = Field("QUEUED", description="Trạng thái ban đầu")
    created_at: str = Field(..., description="Thời gian tạo")
    message: str = Field("Yêu cầu đã được tiếp nhận và đưa vào hàng đợi xử lý.")


class JobStatusResponse(BaseModel):
    job_id: str
    url: str
    status: str
    stage: str
    progress_pct: int
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class AccessUrls(BaseModel):
    local_url: str = Field("http://127.0.0.1:8000")
    public_tunnel_url: Optional[str] = None
    tunnel_provider: str = "none"
    is_tunnel_active: bool = False


class HealthResponse(BaseModel):
    status: str = "HEALTHY"
    access_urls: AccessUrls
    gpu_available: bool = False
    gpu_name: Optional[str] = None
    onnx_provider: str = "CUDAExecutionProvider"
    vram_used_mb: Optional[int] = None
    vram_total_mb: Optional[int] = None
    models_loaded: Dict[str, bool] = Field(default_factory=dict)
