"""
Module test_vlm_extractor: Kiểm thử độc lập Module 4 - Prompt Builder, Text Normalizer, Anti-hallucination & JSON Parser v2.
"""

import unittest
from unittest.mock import MagicMock
from PIL import Image
import numpy as np
import torch

from src.vlm.prompt_builder import (
    build_prompt,
    build_step1_context_prompt,
    build_step2_ocr_prompt,
    build_step3_conclude_prompt,
)
from src.vlm.text_normalizer import (
    normalize_stt_text,
    clean_extracted_value,
    extract_regex_anchors,
    parse_json_output,
    validate_address_entities,
)
from src.vlm.vintern_extractor import Vintern1BExtractor


class TestVlmExtractor(unittest.TestCase):
    def test_normalize_stt_text_vietnamese_numbers(self):
        # Kiểm tra chuẩn hóa số chữ sang số tự nhiên
        raw_text = "Quán nằm ở số ba mươi tám đường Nguyễn Huệ, liên hệ không chín không năm một hai ba bốn năm sáu"
        norm = normalize_stt_text(raw_text)
        self.assertIn("38", norm)
        self.assertIn("0905123456", norm)

        # Số phức hợp
        raw_complex = "Giá chỉ hai mươi mốt nghìn một bát, mở cửa lúc tám giờ ba mươi"
        norm_complex = normalize_stt_text(raw_complex)
        self.assertIn("21", norm_complex)
        self.assertIn("8", norm_complex)

    def test_clean_extracted_value_hallucinations(self):
        self.assertIsNone(clean_extracted_value("không có"))
        self.assertIsNone(clean_extracted_value("đang cập nhật"))
        self.assertIsNone(clean_extracted_value("xem trên video"))
        self.assertIsNone(clean_extracted_value("chưa rõ địa chỉ"))
        self.assertIsNone(clean_extracted_value("n/a"))
        self.assertIsNone(clean_extracted_value("None"))
        self.assertIsNone(clean_extracted_value("BẮT BUỘC"))
        self.assertIsNone(clean_extracted_value("123 đường nguyễn văn cừ"))
        self.assertIsNone(clean_extracted_value("10.75%"))
        self.assertIsNone(clean_extracted_value("0.81"))

        # Giá trị hợp lệ được giữ lại và làm sạch khoảng trắng
        valid_val = "  Quán Cơm Tấm Ba Ghiền   "
        self.assertEqual(clean_extracted_value(valid_val), "Quán Cơm Tấm Ba Ghiền")

    def test_fast_path_conclude(self):
        """Kiểm tra cơ chế Fast-Path trong conclude() khi có <= 1 ứng viên duy nhất."""
        extractor = Vintern1BExtractor(auto_load=False)
        extractor.frame_evidence = [
            {"frame_idx": 1, "tên_quán": "Ốc Nóng Hà Trang", "địa_chỉ": "1A Đinh Liệt", "temporal_zone": "intro"},
            {"frame_idx": 3, "tên_quán": "Ốc Nóng Hà Trang", "địa_chỉ": "1A Đinh Liệt", "temporal_zone": "outro"},
        ]
        res = extractor.conclude()
        self.assertEqual(res["tên_quán"], "Ốc Nóng Hà Trang")
        self.assertEqual(res["địa_chỉ"], "1A Đinh Liệt")
        self.assertEqual(res["confidence_status"], "Cao")
        self.assertIn("Frame 1, Frame 3 (OCR)", res["evidence"]["name_source"])
        self.assertIn("Frame 1, Frame 3 (OCR)", res["evidence"]["address_source"])

    def test_extract_regex_anchors(self):
        script = "Hôm nay mình ghé Quán Cơm Tấm tại số 84 Đặng Văn Bi, Thủ Đức. Hotline: 0988.123.456 nha mọi người."
        anchors = extract_regex_anchors(script)
        self.assertIsNotNone(anchors["regex_address"])
        self.assertIn("84", anchors["regex_address"])
        self.assertIn("Đặng Văn Bi", anchors["regex_address"])
        self.assertEqual(anchors["regex_phone"], "0988123456")

    def test_build_prompts_v2_structure(self):
        # 1. Step 1: Prompt Ngữ cảnh
        p1 = build_step1_context_prompt("Quán Bún Bò Huế tại 45 Lê Duẩn rất ngon.")
        self.assertIn("VĂN BẢN LỜI THOẠI", p1)
        self.assertIn("45 Lê Duẩn", p1)

        # 2. Step 2: Prompt Quét OCR độc lập
        p2 = build_step2_ocr_prompt()
        self.assertIn("<image>", p2)
        self.assertIn("tên_quán", p2)
        self.assertIn("địa_chỉ", p2)
        self.assertIn("chữ_khác_trên_ảnh", p2)

        # 3. Step 3: Prompt Tổng hợp kết luận (Ưu tiên Nguồn 1 OCR)
        ocr_results = [
            {"frame_idx": 0, "tên_quán": "Quán Cây Bàng", "địa_chỉ": "123 Hoàng Diệu"},
            {"frame_idx": 1, "tên_quán": "Cây Bàng Quán", "địa_chỉ": "123 Hoàng Diệu"},
        ]
        context_data = {"tên_quán": "Cây Bàng", "địa_chỉ": "Hoàng Diệu"}
        p3 = build_step3_conclude_prompt(ocr_results, context_data)
        self.assertIn("NGUỒN 1 - Chữ đọc trực tiếp từ biển hiệu", p3)
        self.assertIn("NGUỒN 2 - Thông tin bổ trợ", p3)
        self.assertIn("123 Hoàng Diệu", p3)

    def test_select_best_ocr_candidate_majority_voting(self):
        # Giả lập kết quả OCR của 4 frames
        ocr_results = [
            {"frame_idx": 0, "tên_quán": "Bánh Mì Phượng", "địa_chỉ": "2B Phan Chu Trinh, Hội An"},
            {"frame_idx": 1, "tên_quán": "Bánh Mì Phượng", "địa_chỉ": "2B Phan Chu Trinh, Hội An"},
            {"frame_idx": 2, "tên_quán": "Bánh Mì Phượng", "địa_chỉ": "Phan Chu Trinh"},
            {"frame_idx": 3, "tên_quán": None, "địa_chỉ": "Hội An"},
        ]
        best_name = Vintern1BExtractor._select_best_ocr_candidate(ocr_results, "tên_quán")
        best_addr = Vintern1BExtractor._select_best_ocr_candidate(ocr_results, "địa_chỉ")

        self.assertEqual(best_name, "Bánh Mì Phượng")
        # 2B Phan Chu Trinh xuất hiện 2 lần và dài hơn "Phan Chu Trinh"
        self.assertEqual(best_addr, "2B Phan Chu Trinh, Hội An")

    def test_validate_address_entities(self):
        # 1. Địa chỉ chuẩn có cả số nhà và tên đường
        addr1, conf1 = validate_address_entities("123 Hoàng Diệu, Quận Hải Châu, Đà Nẵng")
        self.assertEqual(conf1, "HIGH")
        self.assertEqual(addr1, "123 Hoàng Diệu, Quận Hải Châu, Đà Nẵng")

        # 2. Địa chỉ chỉ có tên đường không có số nhà
        addr2, conf2 = validate_address_entities("Đường Lê Duẩn, Hà Nội")
        self.assertEqual(conf2, "MEDIUM")

        # 3. Chuỗi ảo giác / câu cảm thán không có thực thể địa lý
        addr3, conf3 = validate_address_entities("ngon lắm")
        self.assertIsNone(addr3)
        self.assertEqual(conf3, "UNKNOWN")

    def test_select_best_ocr_candidate_instance_call(self):
        # Kiểm tra gọi _select_best_ocr_candidate trực tiếp trên instance Vintern1BExtractor
        extractor = Vintern1BExtractor(auto_load=False)
        extractor.frame_evidence = [
            {"frame_idx": 1, "tên_quán": "Ốc Nóng Hà Trang", "địa_chỉ": "1A Đinh Liệt"},
            {"frame_idx": 2, "tên_quán": "Ốc Nóng Hà Trang", "địa_chỉ": "1A Đinh Liệt"},
            {"frame_idx": 3, "tên_quán": "Hà Trang", "địa_chỉ": None},
        ]
        best_name, name_src = extractor._select_best_ocr_candidate("tên_quán")
        best_addr, addr_src = extractor._select_best_ocr_candidate("địa_chỉ")

        self.assertEqual(best_name, "Ốc Nóng Hà Trang")
        self.assertIn("Frame", name_src)
        self.assertEqual(best_addr, "1A Đinh Liệt")
        self.assertIn("Frame", addr_src)

    def test_address_time_and_price_filtering(self):
        # Các cụm giờ giấc hoặc số lượng phải bị loại bỏ thành None khi lọc address
        self.assertIsNone(clean_extracted_value("2 giờ chiều là hết", field_type="address"))
        self.assertIsNone(clean_extracted_value("2 giờ chiều nha", field_type="address"))
        self.assertIsNone(clean_extracted_value("40 ca", field_type="address"))
        self.assertIsNone(clean_extracted_value("mở cửa lúc 8h", field_type="address"))

        # Địa chỉ thực tế chứa số và tên đường hợp lệ
        valid = clean_extracted_value("586 Trường Sa, Phú Nhuận", field_type="address")
        self.assertEqual(valid, "586 Trường Sa, Phú Nhuận")


    def test_parse_json_output_variants(self):
        sample1 = '```json\n{"tên_quán": "Bánh Mì Phượng", "địa_chỉ": "2B Phan Chu Trinh, Hội An"}\n```'
        res1 = parse_json_output(sample1)
        self.assertEqual(res1["tên_quán"], "Bánh Mì Phượng")
        self.assertEqual(res1["địa_chỉ"], "2B Phan Chu Trinh, Hội An")
        self.assertEqual(res1["confidence_status"], "HIGH")

    def test_process_frame_numpy_bgr_conversion(self):
        """Kiểm tra process_frame() chuyển đổi mảng OpenCV BGR ndarray (cv2.cvtColor) an toàn không lỗi."""
        extractor = Vintern1BExtractor(auto_load=False)
        extractor.model = MagicMock()
        extractor.tokenizer = MagicMock()
        extractor.transform = MagicMock(return_value=torch.zeros((3, 448, 448)))
        dummy_bgr = np.zeros((480, 640, 3), dtype=np.uint8)
        dummy_bgr[10:50, 10:50] = (255, 0, 0)

        extractor.model.chat.return_value = (
            '```json\n{"tên_quán": "Quán Test OpenCV", "địa_chỉ": "123 Đường Test"}\n```',
            []
        )

        ocr_result = extractor.process_frame(dummy_bgr, frame_idx=1)
        self.assertEqual(ocr_result["tên_quán"], "Quán Test OpenCV")
        self.assertEqual(ocr_result["địa_chỉ"], "123 Đường Test")

    def test_conclude_prevents_hallucinated_address_when_evidence_is_none(self):
        """
        Kiểm tra cơ chế triệt tiêu ảo giác trong conclude():
        Khi các frame chỉ có tên quán ('Gia Su', 'Bia Suối') mà KHÔNG có địa chỉ,
        dù LLM trả về địa chỉ ảo giác ('1A Đinh Liệt, Hoàn Kiếm, Hà Nội'),
        kết quả cuối cùng BẮT BUỘC địa chỉ phải là None và dẫn chứng là None.
        """
        extractor = Vintern1BExtractor(auto_load=False)
        extractor.frame_evidence = [
            {"frame_idx": 1, "tên_quán": "Gia Su", "địa_chỉ": None, "temporal_zone": "body", "log_line": "Frame 1"},
            {"frame_idx": 2, "tên_quán": "Bia Suối", "địa_chỉ": None, "temporal_zone": "body", "log_line": "Frame 2"},
            {"frame_idx": 3, "tên_quán": None, "địa_chỉ": None, "temporal_zone": "body", "log_line": "Frame 3"},
        ]

        extractor.model = MagicMock()
        extractor.tokenizer = MagicMock()
        # Giả lập LLM tự ý bịa ra địa chỉ không có trong ảnh
        extractor.model.chat.return_value = (
            '```json\n{"tên_quán": "Bia Suối", "địa_chỉ": "1A Đinh Liệt, Hoàn Kiếm, Hà Nội", "độ_tin_cậy": "Cao"}\n```',
            []
        )

        res = extractor.conclude()
        self.assertEqual(res["tên_quán"], "Bia Suối")
        self.assertIsNone(res["địa_chỉ"], "Địa chỉ phải là None khi không có bất kỳ frame nào ghi nhận địa chỉ")
        self.assertIsNone(res["evidence"]["address_source"], "Nguồn địa chỉ phải là None")
        self.assertEqual(res["evidence"]["name_source"], "Frame 2 (OCR)")


if __name__ == "__main__":
    unittest.main()
