"""
Module text_normalizer: Tiện ích chuẩn hóa văn bản STT, lọc nhiễu OCR, chống Hallucination và Parse JSON an toàn.
Tham chiếu kiến trúc: Vintern1B_v2.ipynb & build_server.md.
"""

import re
import json
from typing import Optional, Dict, Any, List, Tuple

# Danh sách các cụm từ nhiễu phổ biến do Prompt Echo hoặc Hallucination của Qwen2-0.5B
HALLUCINATED_PHRASES: List[str] = [
    "bắt buộc", "bát buộc", "quán bát buộc", "quán bắt buộc",
    "123 nguyễn du", "123 đường nguyễn văn cừ", "123 nguyễn văn cừ", "123 nguyễn trãi",
    "địa chỉ cụ thể không rõ", "không có thông tin", "chữ tên quán đọc được",
    "chữ địa chỉ", "trích nguyên văn", "những quán ăn ngon", "các quán ăn ngon",
    "quán ăn ngon", "đến hà nội thì ăn gì", "ăn gì ở", "review quán",
    "đang cập nhật", "chưa rõ", "chưa rõ địa chỉ", "chưa có", "xem trên video",
    "xem video", "trên màn hình", "trong video"
]


def normalize_stt_text(text: str) -> str:
    """
    Chuyển đổi các số viết bằng chữ trong STT tiếng Việt sang chữ số (hỗ trợ hàng trăm, chục, đơn vị, chuỗi số đọc rời).
    Giúp đồng bộ kịch bản lời thoại với chữ số trên biển hiệu thực tế.
    """
    if not text:
        return ""

    digit_map = {
        "không": "0", "linh": "0", "lẻ": "0",
        "một": "1", "mốt": "1", "hai": "2", "ba": "3", "bốn": "4", "tư": "4",
        "năm": "5", "lăm": "5", "sáu": "6", "bảy": "7", "bẩy": "7", "tám": "8", "chín": "9"
    }

    normalized = text

    # 1. Xử lý chuỗi chữ số đơn lẻ đọc rời liên tiếp (>= 3 số liên tiếp: VD SĐT "không chín không năm một hai ba bốn năm sáu" -> "0905123456")
    digits_word_pattern = (
        r'\b(không|linh|lẻ|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|bẩy|tám|chín)'
        r'(?:\s+(không|linh|lẻ|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|bẩy|tám|chín)){2,}\b'
    )

    def repl_digits_seq(m):
        words = m.group(0).lower().split()
        return "".join(digit_map.get(w, "") for w in words)

    normalized = re.sub(digits_word_pattern, repl_digits_seq, normalized, flags=re.IGNORECASE)

    # 2. Xử lý cụm 4 chữ số đọc rời (VD: "một chín tám bảy" -> "1987")
    pattern_4digits = (
        r'\b(một|hai)\s+(không|chín|tám)\s+(không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s+'
        r'(không|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín)\b'
    )

    def repl_4d(m):
        return "".join(digit_map[w.lower()] for w in m.groups())

    normalized = re.sub(pattern_4digits, repl_4d, normalized, flags=re.IGNORECASE)

    # 3. Xử lý số hàng trăm đầy đủ: "<chữ> trăm <chữ> mươi <chữ>" (VD: "năm trăm tám mươi sáu" -> "586")
    pattern_hundreds_full = (
        r'\b(một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s+trăm\s+(mười|hai|ba|bốn|năm|sáu|bảy|tám|chín)'
        r'(?:\s+mươi)?(?:\s+(một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín))?\b'
    )

    def repl_hundreds(m):
        h = digit_map[m.group(1).lower()]
        t_word = m.group(2).lower()
        t = "1" if t_word == "mười" else digit_map[t_word]
        u = digit_map[m.group(3).lower()] if m.group(3) else "0"
        return f"{h}{t}{u}"

    normalized = re.sub(pattern_hundreds_full, repl_hundreds, normalized, flags=re.IGNORECASE)

    # 4. Xử lý số hàng trăm có "linh/lẻ": "<chữ> trăm linh/lẻ <chữ>" (VD: "hai trăm linh năm" -> "205")
    pattern_hundreds_zero = (
        r'\b(một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s+trăm\s+(?:linh|lẻ)\s+'
        r'(một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\b'
    )
    normalized = re.sub(
        pattern_hundreds_zero,
        lambda m: f"{digit_map[m.group(1).lower()]}0{digit_map[m.group(2).lower()]}",
        normalized,
        flags=re.IGNORECASE
    )

    # 5. Xử lý số hàng chục: "<chữ> mươi <chữ>" (VD: "ba mươi tư" -> "34", "ba mươi" -> "30")
    pattern_tens = (
        r'\b(hai|ba|bốn|năm|sáu|bảy|tám|chín)\s+mươi(?:\s+(mốt|một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín))?\b'
    )

    def repl_tens(m):
        t = digit_map[m.group(1).lower()]
        u = digit_map[m.group(2).lower()] if m.group(2) else "0"
        return f"{t}{u}"

    normalized = re.sub(pattern_tens, repl_tens, normalized, flags=re.IGNORECASE)

    # 6. Xử lý "mười <chữ>" (VD: "mười lăm" -> "15")
    pattern_teens = r'\bmười(?:\s+(một|hai|ba|bốn|năm|lăm|sáu|bảy|tám|chín))?\b'
    normalized = re.sub(
        pattern_teens,
        lambda m: f"1{digit_map[m.group(1).lower()]}" if m.group(1) else "10",
        normalized,
        flags=re.IGNORECASE
    )

    # 7. Xử lý số đơn lẻ đi sau từ khóa chỉ địa chỉ (số, ngõ, hẻm, khu, quận)
    pattern_single_after_kw = r'\b(số|ngõ|ngách|hẻm|khu|quận|phường)\s+(một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\b'
    normalized = re.sub(
        pattern_single_after_kw,
        lambda m: f"{m.group(1)} {digit_map[m.group(2).lower()]}",
        normalized,
        flags=re.IGNORECASE
    )

    # 8. Xử lý số đơn lẻ đi trước đơn vị thời gian / tiền tệ (giờ, phút, nghìn, k)
    pattern_number_before_unit = r'\b(một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\s+(giờ|phút|nghìn|ngàn|k)\b'
    normalized = re.sub(
        pattern_number_before_unit,
        lambda m: f"{digit_map[m.group(1).lower()]} {m.group(2)}",
        normalized,
        flags=re.IGNORECASE
    )

    return normalized


def clean_extracted_value(val: Optional[str], field_type: str = "general") -> Optional[str]:
    """
    Làm sạch và lọc bỏ các giá trị rác, prompt echo, chỉ số confidence DBNet hoặc hallucination.
    """
    if val is None:
        return None
    val_str = str(val).strip().strip('"\'.,;-:')
    if not val_str:
        return None

    val_lower = val_str.lower()

    # 1. Lọc các token rỗng/null cơ bản
    invalid_exact = {
        "null", "none", "chưa rõ", "không rõ", "không có", "n/a", "na",
        "unknown", "<null>", "không", "trống", "follow", "like", "share"
    }
    if val_lower in invalid_exact or val_str.startswith("<"):
        return None

    # 2. Lọc các cụm từ hallucination / prompt echo
    for phrase in HALLUCINATED_PHRASES:
        if phrase in val_lower:
            return None

    # 3. Xóa các chỉ số confidence/bounding box của DBNet bị lọt vào đầu/cuối chuỗi (VD: "0.81 THỊT XIÊN...", "10.75%")
    val_str = re.sub(r'^(?:\d+\.\d+%?\s*)+', '', val_str).strip()
    val_str = re.sub(r'\b(?:Area|DT)\s*:\s*\d+(?:\.\d+)?%?\b', '', val_str, flags=re.IGNORECASE).strip()
    if not val_str:
        return None
    val_lower = val_str.lower()

    # 4. Nếu chuỗi chỉ toàn số, phần trăm, giờ giấc (VD: "1186", "10.75%", "17:00 - 20:00") -> loại bỏ
    if re.match(r'^[\d\s.,:%+-]+$', val_str):
        return None

    # 5. Kiểm tra riêng cho trường tên quán: không lấy câu mô tả quá dài (> 8 từ) hoặc chứa từ khóa so sánh
    if field_type == "name":
        descriptive_stopwords = ["đông khách nhất", "ngon nhất", "rẻ nhất", "nổi tiếng nhất", "bình dân đông khách"]
        if any(sw in val_lower for sw in descriptive_stopwords):
            return None
        # Nếu tên quán bị nhận nhầm là một địa chỉ thuần túy (VD: "586 Trường Sa, Phú Nhuận")
        if re.match(r'^\d+[A-Za-z]?\s+(?:đường|phố|ngõ|hẻm)?\s*[A-ZÀ-Ỹ]', val_str) and ("," in val_str):
            return None

    # 6. Kiểm tra riêng cho trường địa chỉ: phải có độ dài tối thiểu và không phải cụm thời gian / giá tiền
    if field_type == "address":
        if len(val_str) < 4:
            return None
        time_or_price_patterns = [
            r'^\d+\s*(?:giờ|phút|tiếng)\s*(?:chiều|sáng|trưa|tối)?(?:\s*(?:là\s*hết|hết|nha|nhé|đến|\-|\:)|$)',
            r'^\d+\s*h\s*(?:chiều|sáng|trưa|tối)?(?:\s*(?:là\s*hết|hết|nha|nhé|đến|\-|\:)|$)',
            r'(?:giờ|h\b)\s*(?:chiều|sáng|trưa|tối)\s*(?:là\s*hết|nha|nhé|đóng|mở)',
            r'^(?:mở\s*cửa|đóng\s*cửa|bán\s*từ|bán\s*đến)\b',
            r'^\d+\s*(?:k|nghìn|ngàn|ca|tiền)\b',
        ]
        for pat in time_or_price_patterns:
            if re.search(pat, val_lower):
                return None

    return val_str


def extract_regex_anchors(text: str) -> Dict[str, Optional[str]]:
    """
    Dùng Regex bắt nhanh các cụm từ khóa chỉ tên quán/địa chỉ/SĐT trong văn bản STT làm fallback an toàn.
    Tuân thủ thiết kế chặt chẽ của Vintern1B_v2.ipynb: chỉ bắt địa chỉ khi có từ khóa địa giới rõ ràng.
    """
    if not text:
        return {"regex_name": None, "regex_addr": None, "regex_address": None, "regex_phone": None}

    name_hint, addr_hint, phone_hint = None, None, None

    # Bắt tên quán sau các cụm giới thiệu trực tiếp
    m_name = re.search(
        r'(?:đây là quán|quán tên là|tại quán|ở quán|chỗ|ghé)\s+([A-ZÀ-Ỹa-zà-ỹ0-9\s]{2,35}?)(?:\s+ở|\s+tại|\s+số|\s+ngõ|\s+đường|\s+phố|\s+quận|\s+mở|\s+nha|\s+nhé|\.|$)',
        text, re.IGNORECASE
    )
    if m_name:
        cand = clean_extracted_value(m_name.group(1).strip(), field_type="name")
        if cand and len(cand.split()) <= 7:
            name_hint = cand

    # Bắt địa chỉ: tìm cụm bắt đầu bằng 'ở/tại/địa chỉ' hoặc các từ khóa địa giới (số, ngõ, hẻm, đường, phố, khu)
    m_addr = re.search(
        r'(?:ở|tại|địa chỉ:?|địa chỉ quán:?)\s+((?:số\s+\d+|ngõ\s+\d+|hẻm\s+\d+|\d+\s+[A-ZÀ-Ỹa-zà-ỹ]+|đường\s+[^.,\n]{3,30}|phố\s+[^.,\n]{3,30}|khu\s+\d+[^.,\n]{3,35})[^.,\n]{0,50})',
        text, re.IGNORECASE
    )
    if not m_addr:
        # Regex theo Vintern1B_v2.ipynb: bắt buộc có từ khóa địa giới hoặc số nhà + tên đường rõ ràng
        m_addr = re.search(
            r'((?:số\s+\d+|ngõ\s+\d+|hẻm\s+\d+|đường\s+[^.,\n]{3,30}|phố\s+[^.,\n]{3,30}|khu\s+\d+[^.,\n]{3,35}|\b\d+[a-zA-Z]?\s+(?:đường\s+|phố\s+|ngõ\s+|hẻm\s+)[A-ZÀ-Ỹa-zà-ỹ\s]{3,30}))(?:\.|,|;|\s+hotline|\s+sđt|\s+nha|\s+nhé|$)',
            text, re.IGNORECASE
        )
    if m_addr:
        addr_hint = clean_extracted_value(m_addr.group(1).strip(), field_type="address")

    # Bắt số điện thoại
    clean_num_text = re.sub(r'[\.\-\s]', '', text)
    m_phone = re.search(r'(?:hotline|sđt|tel|liên hệ)?[:\s]*(0\d{9,10})(?:\D|$)', clean_num_text, re.IGNORECASE)
    if not m_phone:
        m_phone = re.search(r'(0\d{9,10})(?:\D|$)', clean_num_text)
    if m_phone:
        phone_hint = m_phone.group(1)

    return {
        "regex_name": name_hint,
        "regex_addr": addr_hint,
        "regex_address": addr_hint,
        "regex_phone": phone_hint,
    }


def validate_address_entities(address: Optional[str]) -> Tuple[Optional[str], str]:
    """
    Xác thực thực thể địa chỉ:
    - HIGH: Có số nhà và tên đường/phố/ngõ/hẻm hoặc quận/huyện/tỉnh.
    - MEDIUM: Có tên đường hoặc khu vực nhưng không có số nhà cụ thể.
    - UNKNOWN: Ảo giác, rỗng hoặc câu cảm thán không có yếu tố địa lý.
    """
    if not address or not isinstance(address, str):
        return None, "UNKNOWN"

    cleaned = clean_extracted_value(address, field_type="address")
    if not cleaned:
        return None, "UNKNOWN"

    has_street_number = bool(re.search(r'\b\d+([a-zA-Z]|\/\d+)?\b', cleaned))
    has_street_or_area = bool(
        re.search(r'\b(đường|phố|ngõ|ngách|hẻm|quận|huyện|thị xã|tp|thành phố|tỉnh|phường|xã)\b', cleaned, re.IGNORECASE)
    )

    if has_street_number and (has_street_or_area or len(cleaned.split()) >= 3):
        return cleaned, "HIGH"
    elif has_street_or_area or len(cleaned.split()) >= 3:
        return cleaned, "MEDIUM"
    return None, "UNKNOWN"


def parse_json_output(text: str) -> Dict[str, Any]:
    """
    Trích xuất dict từ chuỗi JSON kết quả của mô hình một cách an toàn và áp dụng clean_extracted_value.
    Tự động chuẩn hóa confidence_status dựa trên kiểm thực địa lý.
    """
    raw_dict = {}
    try:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        raw_json = match.group(1).strip() if match else None
        if not raw_json:
            match = re.search(r"(\{[\s\S]*\})", text)
            raw_json = match.group(1).strip() if match else text.strip()
        raw_dict = json.loads(raw_json)
    except Exception:
        name_match = re.search(r'["\'](?:tên_quán|tên_quán_tiềm_năng)["\']\s*:\s*["\']([^"\']+)["\']', text)
        addr_match = re.search(r'["\'](?:địa_chỉ|địa_chỉ_tiềm_năng)["\']\s*:\s*["\']([^"\']+)["\']', text)
        other_match = re.search(r'["\']chữ_khác_trên_ảnh["\']\s*:\s*["\']([^"\']+)["\']', text)
        raw_dict = {
            "tên_quán": name_match.group(1) if name_match else None,
            "địa_chỉ": addr_match.group(1) if addr_match else None,
            "chữ_khác_trên_ảnh": other_match.group(1) if other_match else None,
        }

    cleaned: Dict[str, Any] = {}
    for k, v in raw_dict.items():
        if isinstance(v, dict):
            cleaned[k] = v
        elif "tên_quán" in k:
            cleaned[k] = clean_extracted_value(v, field_type="name")
        elif "địa_chỉ" in k:
            cleaned[k] = clean_extracted_value(v, field_type="address")
        else:
            cleaned[k] = clean_extracted_value(v, field_type="general")

    if "confidence_status" not in cleaned or not cleaned["confidence_status"]:
        addr = cleaned.get("địa_chỉ")
        _, conf = validate_address_entities(addr)
        cleaned["confidence_status"] = conf

    return cleaned
