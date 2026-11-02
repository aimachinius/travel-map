"""
Package detectors: Các module phát hiện phân cảnh và trích chọn khung hình văn bản.
"""

from .scene_detector import SceneDetector
from .text_detector import ONNXTextDetector
from .frame_selector import TextKeyframeSelector, FrameCandidate

__all__ = [
    "SceneDetector",
    "ONNXTextDetector",
    "TextKeyframeSelector",
    "FrameCandidate",
]
