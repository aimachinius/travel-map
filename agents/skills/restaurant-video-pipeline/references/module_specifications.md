# Module Specifications & Interface Contracts

Tài liệu đặc tả chi tiết các interface, dataclass và luồng dữ liệu giữa các module trong `src/`.

---

## 1. Dữ liệu Đầu vào & Đầu ra (Data Contracts)

### 1.1. Keyframe Candidate (`FrameCandidate`)
```python
from dataclasses import dataclass
from typing import Dict, Any, Optional
import numpy as np

@dataclass
class FrameCandidate:
    scene_index: int
    frame_number: int
    timestamp_sec: float
    timestamp_str: str
    text_metrics: Dict[str, Any]  # box_count, avg_score, text_area_ratio, composite_score
    image_bgr: Optional[np.ndarray] = None  # Giữ trong RAM khi cần vẽ hoặc nạp VLM
```

### 1.2. Kết quả Trích xuất Quán ăn (`RestaurantExtractionResult`)
```python
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class RestaurantExtractionResult:
    video_id: str
    restaurant_name: Optional[str]
    address: Optional[str]
    confidence_notes: Optional[str] = None
    selected_frames_count: int = 0
    raw_vlm_output: Optional[str] = None
    execution_time_sec: float = 0.0
    status: str = "SUCCESS"  # SUCCESS, NO_FRAMES, VLM_ERROR, INVALID_VIDEO
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "restaurant_name": self.restaurant_name,
            "address": self.address,
            "confidence_notes": self.confidence_notes,
            "selected_frames_count": self.selected_frames_count,
            "raw_vlm_output": self.raw_vlm_output,
            "execution_time_sec": round(self.execution_time_sec, 2),
            "status": self.status,
            "error_message": self.error_message,
        }
```

---

## 2. Đặc tả Giao diện từng Module

### 2.1. `src/detectors/scene_detector.py`
```python
class SceneDetector:
    def __init__(self, detector_type: str = "content", threshold: float = 27.0, min_scene_len: int = 15):
        ...

    def detect_scenes(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Quét video và trả về danh sách các phân cảnh:
        [{
            "scene_index": 1,
            "start_frame": 0,
            "end_frame": 120,
            "middle_frame": 60,
            "middle_time_sec": 2.0,
            "middle_time_str": "00:00:02.000"
        }, ...]
        """
        ...
```

### 2.2. `src/detectors/text_detector.py`
```python
class ONNXTextDetector:
    def __init__(self, model_dir: str = "tham_khao/onnx", device_id: Optional[int] = None):
        ...

    def evaluate_frame(self, image_bgr: np.ndarray) -> Dict[str, Any]:
        """
        Chấm điểm văn bản trên frame:
        Returns: {
            "box_count": int,
            "avg_score": float,
            "text_area_ratio": float,
            "text_area_pct": float,
            "composite_score": float,
            "dt_boxes": list,
            "scores": list
        }
        """
        ...
```

### 2.3. `src/detectors/frame_selector.py`
```python
class TextKeyframeSelector:
    def __init__(self, scene_detector: SceneDetector, text_detector: ONNXTextDetector, top_k: int = 5, sort_by: str = "composite"):
        ...

    def select_frames(self, video_path: str) -> List[FrameCandidate]:
        """
        Điều phối: Mở video -> Lấy cảnh -> Trích middle frame -> Chấm text metrics -> Sắp xếp & lọc Top-K
        """
        ...
```

### 2.4. `src/vlm/vintern_extractor.py`
```python
class Vintern1BExtractor:
    def __init__(self, model_id: str = "5CD-AI/Vintern-1B-v3_5", device: Optional[str] = None):
        ...

    def extract_info(self, frames: List[Image.Image], script: str) -> Dict[str, Optional[str]]:
        """
        Tiền xử lý dynamic resolution -> Chat inference -> Parse JSON:
        Returns: {"tên_quán": "...", "địa_chỉ": "..."}
        """
        ...
```

### 2.5. `src/pipeline/restaurant_pipeline.py`
```python
class RestaurantExtractorPipeline:
    def __init__(self, frame_selector: TextKeyframeSelector, vlm_extractor: Vintern1BExtractor):
        ...

    def process_video(self, video_path: str, script: str, video_id: Optional[str] = None) -> RestaurantExtractionResult:
        """
        Thực thi end-to-end cho 1 video:
        1. Trích chọn Top-K keyframe chứa text
        2. Chuyển đổi sang PIL Image
        3. Suy luận qua Vintern-1B kèm script
        4. Chuẩn hóa kết quả trả về RestaurantExtractionResult
        """
        ...
```

---

## 3. Quản lý Cấu hình Tập trung (`src/config/settings.py`)

```python
from dataclasses import dataclass
import os

@dataclass
class PipelineConfig:
    # Model configs
    text_model_dir: str = "tham_khao/onnx"
    vlm_model_id: str = "5CD-AI/Vintern-1B-v3_5"
    
    # Scene detection configs
    scene_detector_type: str = "content"
    scene_threshold: float = 27.0
    min_scene_len: int = 15
    
    # Text frame selection
    top_k_frames: int = 4
    sort_by: str = "composite"  # composite, area_ratio, avg_score, box_count
    min_text_score: float = 0.4
    min_text_area_ratio: float = 0.0005
    
    # VLM preprocessing
    max_dynamic_patches: int = 4
    vlm_max_new_tokens: int = 256
    vlm_temperature: float = 0.1
    
    # Output dirs
    output_dir: str = "output"
```
