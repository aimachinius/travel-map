"""
Module io_utils: Các tiện ích xử lý vào/ra an toàn, hỗ trợ đường dẫn Unicode/tiếng Nhật trên Windows.
"""

import os
import csv
import json
from typing import List, Dict, Any, Optional
import cv2
import numpy as np


def format_timestamp(seconds: float) -> str:
    """
    Chuyển đổi số giây thành chuỗi định dạng HH:MM:SS.mmm
    """
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def cv2_imread(path: str, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    """
    Đọc ảnh an toàn trên Windows hỗ trợ đường dẫn Unicode / tiếng Nhật như 'マイドライブ'.
    """
    if not os.path.exists(path):
        return None
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if len(data) == 0:
            return None
        return cv2.imdecode(data, flags)
    except Exception:
        try:
            return cv2.imread(path, flags)
        except Exception:
            return None


def cv2_imwrite(path: str, img: np.ndarray) -> bool:
    """
    Ghi ảnh an toàn trên Windows hỗ trợ đường dẫn Unicode / tiếng Nhật như 'マイドライブ'.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = ".jpg"
        ret, buf = cv2.imencode(ext, img)
        if ret:
            buf.tofile(path)
            return True
        return False
    except Exception:
        try:
            return cv2.imwrite(path, img)
        except Exception:
            return False


def draw_detection_boxes(
    img: np.ndarray,
    dt_boxes: List[Any],
    scores: Optional[List[float]] = None
) -> np.ndarray:
    """
    Vẽ các bounding box và điểm tin cậy lên ảnh (để kiểm tra trực quan).
    """
    drawn = img.copy()
    for idx, box in enumerate(dt_boxes):
        pts = np.array(box, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(drawn, [pts], True, (0, 255, 0), 2)

        if scores is not None and idx < len(scores):
            score_val = scores[idx]
            pt_text = (int(box[0][0]), max(15, int(box[0][1]) - 5))
            label = f"{score_val:.2f}"
            cv2.putText(
                drawn,
                label,
                pt_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
                cv2.LINE_AA,
            )
    return drawn


def read_csv_as_dicts(csv_path: str, encoding: str = "utf-8-sig") -> List[Dict[str, str]]:
    """
    Đọc file CSV thành danh sách các dictionary, tự động xử lý UTF-8 BOM.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Không tìm thấy file CSV: {csv_path}")

    records = []
    with open(csv_path, mode="r", encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append({k.strip(): (v.strip() if v else "") for k, v in row.items()})
    return records


def save_json_file(data: Any, file_path: str, indent: int = 2) -> bool:
    """
    Lưu dữ liệu ra file JSON an toàn với tiếng Việt (ensure_ascii=False).
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, mode="w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        return True
    except Exception:
        return False
