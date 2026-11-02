"""
Module prompt_builder: Xây dựng các mẫu prompt chuẩn cho kiến trúc 4 bước tuần tự của Vintern-1B.
Tích hợp Đảo chiều ưu tiên Nguồn 1 OCR và loại bỏ các từ kích hoạt ảo giác (Neutral Prompts).
"""

from typing import Optional, Dict, Any
from .text_normalizer import parse_json_output

__all__ = [
    "build_step1_context_prompt",
    "build_step2_ocr_prompt",
    "build_step3_conclude_prompt",
    "build_prompt",
    "parse_json_output",
]


def build_step1_context_prompt(
    norm_script: str,
    comments_text: str = "",
    anchors: Optional[Dict[str, Optional[str]]] = None
) -> str:
    """
    BƯỚC 1: Xây dựng prompt trích xuất nguyên văn (Extractive) từ Script & Comments.
    Tuân thủ đúng thiết kế gốc của Vintern1B_v2.ipynb: không đưa cụm Regex vào prompt
    để tránh mô hình 0.5B bị Prompt Echo hoặc neo vào các từ suy diễn sai.
    """
    return f"""Trích xuất nguyên văn Tên quán ăn và Địa chỉ được nhắc đến trong văn bản dưới đây.
Quy tắc:
- Chỉ trích xuất thông tin thực sự có trong văn bản, không tự suy diễn.
- Không lấy câu mô tả dài (ví dụ: "quán đông khách nhất...") làm tên quán.
- Nếu không có tên quán hoặc địa chỉ cụ thể, điền null.

VĂN BẢN LỜI THOẠI:
"{norm_script if norm_script else 'Không có'}"

BÌNH LUẬN:
"{comments_text if comments_text else 'Không có'}"

Trả về đúng định dạng JSON sau:
{{
  "tên_quán_tiềm_năng": "<tên quán hoặc null>",
  "địa_chỉ_tiềm_năng": "<số nhà, tên đường/phố, quận hoặc null>"
}}"""


def build_step2_ocr_prompt() -> str:
    """
    BƯỚC 2: Prompt thuần OCR thị giác trên từng khung hình sạch.
    Sử dụng câu lệnh trung tính, tuyệt đối không dùng từ in hoa "BẮT BUỘC" để tránh Prompt Echo.
    """
    return """<image>
Hãy đọc văn bản tiếng Việt xuất hiện trên biển hiệu hoặc phụ đề trong ảnh để tìm tên quán và địa chỉ.
Lưu ý:
- Chỉ ghi lại chữ thực sự nhìn thấy rõ trong ảnh.
- Bỏ qua các con số thập phân nhỏ (như 0.81, 0.92) hoặc phần trăm diện tích.
- Nếu không có tên quán hoặc địa chỉ trong ảnh, hãy để giá trị là null.

Chỉ trả về JSON:
{
  "tên_quán": "<chữ tên quán đọc được trên ảnh hoặc null>",
  "địa_chỉ": "<chữ địa chỉ/số nhà/tên đường đọc được trên ảnh hoặc null>",
  "chữ_khác_trên_ảnh": "<các chữ đáng chú ý khác đọc được hoặc null>"
}"""


def build_step3_conclude_prompt(
    frames_text: Any,
    best_ocr_name: Optional[Any] = None,
    best_ocr_addr: Optional[str] = None,
    text_section: str = ""
) -> str:
    """
    BƯỚC 3: Prompt tổng hợp kết luận Đảo Chiều Ưu Tiên Nguồn 1 OCR (trên biển hiệu) lên đầu.
    Không in chữ 'null' trong phần văn bản để tránh mô hình Qwen2-0.5B neo vào null.
    """
    if isinstance(frames_text, list):
        ocr_list = frames_text
        context_data = best_ocr_name if isinstance(best_ocr_name, dict) else {}
        lines = []
        for e in ocr_list:
            parts = []
            if e.get("tên_quán"):
                parts.append(f"Tên quán='{e['tên_quán']}'")
            if e.get("địa_chỉ"):
                parts.append(f"Địa chỉ='{e['địa_chỉ']}'")
            if e.get("chữ_khác") or e.get("đặc_trưng"):
                parts.append(f"Chữ khác='{e.get('chữ_khác') or e.get('đặc_trưng')}'")
            if parts:
                lines.append(f"- Frame {e.get('frame_idx', 1)}: " + ", ".join(parts))
        frames_text_str = "\n".join(lines) if lines else "Không có chữ trên ảnh."
        best_ocr_name_str = context_data.get("tên_quán")
        best_ocr_addr_str = context_data.get("địa_chỉ")
        text_section_str = (
            f"- Tên quán từ lời thoại: {best_ocr_name_str}\n- Địa chỉ từ lời thoại: {best_ocr_addr_str}"
            if (best_ocr_name_str or best_ocr_addr_str) else ""
        )
    else:
        frames_text_str = str(frames_text) if frames_text else "Không có chữ trên ảnh."
        best_ocr_name_str = best_ocr_name
        best_ocr_addr_str = best_ocr_addr
        text_section_str = text_section

    ocr_name_display = best_ocr_name_str if best_ocr_name_str else "Chưa có"
    ocr_addr_display = best_ocr_addr_str if best_ocr_addr_str else "Chưa có"

    if not text_section_str or text_section_str.strip() == "Không có thông tin từ lời thoại.":
        return f"""Dựa vào các dòng chữ đọc được từ các khung hình trong video dưới đây, hãy tổng hợp TÊN QUÁN và ĐỊA CHỈ quán ăn đầy đủ và chính xác nhất.

THÔNG TIN ĐỌC ĐƯỢC TỪ CÁC KHUNG HÌNH (OCR EVIDENCE):
{frames_text_str}
- Ứng viên tên quán nổi bật: {ocr_name_display}
- Ứng viên địa chỉ nổi bật: {ocr_addr_display}

Quy tắc BẮT BUỘC:
1. CHỈ sử dụng từ ngữ thực sự xuất hiện trong phần THÔNG TIN ĐỌC ĐƯỢC TỪ CÁC KHUNG HÌNH ở trên.
2. Nếu các khung hình KHÔNG có thông tin địa chỉ hoặc ghi 'Chưa có', giá trị của "địa_chỉ" BẮT BUỘC là null. TUYỆT ĐỐI KHÔNG tự sáng tác, suy đoán hay lấy bất kỳ địa chỉ ví dụ nào!
3. Nếu các khung hình KHÔNG có tên quán hoặc ghi 'Chưa có', giá trị của "tên_quán" BẮT BUỘC là null.
4. Chỉ ghép nối khi các khung hình khác nhau cùng đề cập và bổ sung các thành phần cho nhau (ví dụ: một frame có số nhà tên đường, một frame khác có quận/thành phố).

Trả về JSON:
{{
  "tên_quán": "<Tên quán hoặc null nếu không có trên ảnh>",
  "địa_chỉ": "<Địa chỉ hoặc null nếu không có trên ảnh>",
  "độ_tin_cậy": "Cao"
}}"""

    text_sec_display = text_section_str

    return f"""Dựa vào dữ liệu đã thu thập dưới đây, hãy xác định TÊN QUÁN và ĐỊA CHỈ chính xác nhất.

NGUỒN 1 - Chữ đọc trực tiếp từ biển hiệu trên ảnh (ĐỘ CHÍNH XÁC CAO NHẤT):
{frames_text_str}
- Tên quán rõ nhất trên ảnh: {ocr_name_display}
- Địa chỉ rõ nhất trên ảnh: {ocr_addr_display}

NGUỒN 2 - Thông tin bổ trợ từ lời thoại:
{text_sec_display}

Quy tắc:
1. Ưu tiên tuyệt đối chữ đọc từ biển hiệu ở NGUỒN 1 vì viết đúng chính tả và số nhà.
2. Chỉ dùng NGUỒN 2 khi NGUỒN 1 bị khuyết thiếu.
3. Không tự bịa thêm tên đường hay thành phố không có trong 2 nguồn.

Trả về JSON:
{{
  "tên_quán": "<Tên quán chính xác nhất>",
  "địa_chỉ": "<Địa chỉ chính xác nhất>",
  "độ_tin_cậy": "Cao"
}}"""


def build_prompt(script: str, num_images: int = 1) -> str:
    """
    Hàm tương thích ngược với code cũ (Single-shot multi-image prompt).
    """
    image_tags = "\n".join([f"Khung hình {i+1}: <image>" for i in range(num_images)])
    script_content = script.strip() if script else "Không có kịch bản âm thanh."

    return f"""{image_tags}
Kịch bản lời thoại: "{script_content}"
Nhiệm vụ: Dựa vào hình ảnh các khung hình từ video và kịch bản lời thoại trên, hãy trích xuất chính xác tên quán ăn và địa chỉ của quán.

Quy tắc:
1. Ưu tiên chữ đọc từ biển hiệu trên hình ảnh.
2. Chỉ trả về kết quả dưới định dạng JSON hợp lệ:
{{
  "tên_quán": "<Tên quán chính xác hoặc null>",
  "địa_chỉ": "<Địa chỉ cụ thể hoặc null>"
}}"""
