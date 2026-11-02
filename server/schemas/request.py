"""
Module request: Pydantic schemas cho dữ liệu đầu vào của các endpoint.
"""

from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class UrlExtractRequest(BaseModel):
    """
    Dữ liệu yêu cầu bóc tách thông tin quán ăn từ URL video.
    """
    url: str = Field(
        ...,
        description="Đường dẫn video từ TikTok hoặc YouTube Shorts",
        examples=["https://www.youtube.com/shorts/kJQP7kiw5Fk", "https://www.tiktok.com/@user/video/123456789"]
    )
    top_k_frames: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Số lượng keyframe biển hiệu trích chọn tối đa để đưa vào VLM (phân bổ theo hạn ngạch Stratified Top-K)"
    )
    language: Optional[str] = Field(
        default=None,
        description="[Deprecated] Ngôn ngữ nhận dạng STT không còn sử dụng trong bản v3.0"
    )
    force_reload: bool = Field(
        default=False,
        description="Bắt buộc tải lại và suy luận lại dù đã có trong cache"
    )
    keep_raw_video: bool = Field(
        default=False,
        description="Lưu lại file MP4 gốc trên ổ cứng sau khi hoàn tất (mặc định False để tiết kiệm 95% dung lượng đĩa)"
    )


class JobCreateRequest(UrlExtractRequest):
    """
    Dữ liệu yêu cầu đưa vào hàng đợi bất đồng bộ.
    """
    pass
