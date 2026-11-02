"""
Module vintern_extractor: Triển khai kiến trúc Pure Vision Sequential Frame Processing (v3.0)
cho mô hình 5CD-AI/Vintern-1B-v3_5 (Hoàn toàn loại bỏ nhánh STT Script).
Tham chiếu: build_server.md (v3.0).

Quy trình 3 bước cốt lõi:
1. BƯỚC 1: Quét OCR tuần tự từng khung hình sạch (process_frame)
2. BƯỚC 2: Bầu chọn Majority Voting & Kết luận cuối cùng (conclude) kèm cơ chế Fast-Path
3. BƯỚC 3: Dọn dẹp bộ nhớ & Reset Context (clear_context)
"""

import os
import re
import gc
import json
import datetime
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple, Union
import cv2
import numpy as np
from PIL import Image

from .preprocessor import build_transform, dynamic_preprocess
from .text_normalizer import (
    normalize_stt_text,
    clean_extracted_value,
    extract_regex_anchors,
    parse_json_output,
)
from .prompt_builder import (
    build_step1_context_prompt,
    build_step2_ocr_prompt,
    build_step3_conclude_prompt,
    build_prompt,
)
from ..utils.logger import get_logger

logger = get_logger("Vintern1BExtractor")


class Vintern1BExtractor:
    """
    Kiến trúc Pure Vision Sequential Frame Processing (v3.0)
    cho mô hình 5CD-AI/Vintern-1B-v3_5 (Không phụ thuộc STT Script).
    """
    def __init__(
        self,
        model_id: str = "5CD-AI/Vintern-1B-v3_5",
        device: Optional[str] = None,
        max_dynamic_patches: int = 3,
        image_size: int = 448,
        auto_load: bool = False,
    ):
        self.model_id = model_id
        self.max_dynamic_patches = max_dynamic_patches
        self.image_size = image_size
        self.device = device
        self.model = None
        self.tokenizer = None
        self.transform = None
        self.dtype = None

        self.gen_config = dict(
            max_new_tokens=200,
            do_sample=False,
            repetition_penalty=1.05,
        )

        self.current_context: Optional[Dict[str, Any]] = None
        self.frame_evidence: List[Dict[str, Any]] = []

        if auto_load:
            self.load_model()

    def _apply_compatibility_patches(self):
        """Khắc phục lỗi tương thích giữa thư viện Transformers mới (>=4.48) và kiến trúc InternVL."""
        try:
            from transformers.configuration_utils import PretrainedConfig
            from transformers.modeling_utils import PreTrainedModel

            _orig_to_diff_dict = PretrainedConfig.to_diff_dict
            PretrainedConfig.to_diff_dict = lambda self_cfg: (
                _orig_to_diff_dict(self_cfg)
                if not hasattr(self_cfg, "llm_config") or self_cfg.llm_config
                else self_cfg.to_dict()
            )

            if not hasattr(PreTrainedModel, "all_tied_weights_keys"):
                PreTrainedModel.all_tied_weights_keys = property(
                    lambda self_model: getattr(self_model, "_tied_weights_keys", {})
                )
        except Exception as e:
            logger.warning(f"Không thể áp dụng patch tương thích Transformers: {e}")

    def load_model(self):
        """Nạp mô hình và Tokenizer vào bộ nhớ RAM / VRAM."""
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except Exception as e:
            logger.error(
                "Không thể nạp PyTorch hoặc Transformers. Hãy đảm bảo bạn đang chạy trong môi trường "
                f"hỗ trợ PyTorch: {e}"
            )
            raise

        self._apply_compatibility_patches()
        logger.info(f"[*] Đang chuẩn bị nạp mô hình VLM: {self.model_id}...")

        if self.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"

        if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
            self.dtype = torch.bfloat16
        elif torch.cuda.is_available():
            self.dtype = torch.float16
        else:
            self.dtype = torch.float32

        logger.info(f"[*] Thiết bị: {self.device} | Kiểu dữ liệu: {self.dtype}")

        self.model = AutoModel.from_pretrained(
            self.model_id,
            torch_dtype=self.dtype,
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        ).eval()

        if torch.cuda.is_available() and self.device == "cuda":
            self.model = self.model.to(self.device)

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            use_fast=False,
        )

        self.transform = build_transform(input_size=self.image_size)
        logger.info("[✓] Nạp mô hình Vintern-1B và Tokenizer thành công!")

    # =========================================================================
    # BƯỚC 1: QUÉT OCR TUẦN TỰ TỪNG KHUNG HÌNH SẠCH (process_frame)
    # =========================================================================
    def process_frame(
        self,
        frame: Union[Image.Image, np.ndarray, str],
        frame_idx: int = 1,
        total_frames: int = 1,
        candidate_meta: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        BƯỚC 1: Quét OCR độc lập từng khung hình bằng Vintern-1B.
        - dynamic_preprocess (max_num=3, 448x448, use_thumbnail=True).
        - Sử dụng neutral prompt trung tính.
        - Tự động cứu dữ liệu địa chỉ nếu bị model xếp nhầm sang chữ_khác_trên_ảnh.
        """
        if self.model is None or self.tokenizer is None:
            self.load_model()

        import torch

        if isinstance(frame, str):
            frame_img = Image.open(frame).convert("RGB")
        elif isinstance(frame, np.ndarray):
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            else:
                frame_img = Image.fromarray(frame).convert("RGB")
        elif isinstance(frame, Image.Image):
            frame_img = frame.convert("RGB")
        else:
            raise ValueError(f"Khung hình không hợp lệ: {type(frame)}")

        patches = dynamic_preprocess(
            frame_img,
            image_size=self.image_size,
            use_thumbnail=True,
            max_num=self.max_dynamic_patches,
        )
        pixel_tensors = [self.transform(patch) for patch in patches]
        pixel_tensor = torch.stack(pixel_tensors).to(dtype=self.dtype, device=self.device)
        num_patches_list = [pixel_tensor.size(0)]

        prompt = build_step2_ocr_prompt()

        with torch.no_grad():
            response, _ = self.model.chat(
                self.tokenizer,
                pixel_values=pixel_tensor,
                question=prompt,
                generation_config=self.gen_config,
                num_patches_list=num_patches_list,
                history=None,
                return_history=True,
            )

        parsed = parse_json_output(response)

        ocr_name = clean_extracted_value(parsed.get("tên_quán"), field_type="name")
        ocr_addr = clean_extracted_value(parsed.get("địa_chỉ"), field_type="address")
        ocr_other = clean_extracted_value(parsed.get("chữ_khác_trên_ảnh"), field_type="general")

        # Cứu dữ liệu tự động: Nếu model để địa_chỉ là null nhưng đặt địa chỉ vào chữ_khác_trên_ảnh
        if not ocr_addr and ocr_other:
            if re.search(r'(?:đc|địa chỉ|số|ngõ|hẻm|phố|đường|quận|phường)\s*[:.]?\s*\d*', ocr_other, re.IGNORECASE):
                salvaged = clean_extracted_value(
                    re.sub(r'^(?:đc|địa chỉ)\s*[:.]?\s*', '', ocr_other, flags=re.IGNORECASE),
                    field_type="address"
                )
                if salvaged:
                    ocr_addr = salvaged

        temporal_zone = getattr(candidate_meta, "temporal_zone", "body") if candidate_meta else "body"
        timestamp_sec = getattr(candidate_meta, "timestamp_sec", 0.0) if candidate_meta else 0.0
        final_score = getattr(candidate_meta, "final_score", 0.0) if candidate_meta else 0.0

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = (
            f"[{now_str}] [INFO] [Vintern1BExtractor]: [Frame {frame_idx}/{total_frames}] "
            f"({temporal_zone.upper()}) -> Tên OCR: {ocr_name} | Địa chỉ OCR: {ocr_addr} | Chữ khác: {ocr_other}"
        )

        evidence_entry = {
            "frame_idx": frame_idx,
            "total_frames": total_frames,
            "temporal_zone": temporal_zone,
            "timestamp_sec": timestamp_sec,
            "final_score": final_score,
            "tên_quán": ocr_name,
            "địa_chỉ": ocr_addr,
            "đặc_trưng": ocr_other,
            "ocr_name": ocr_name,
            "ocr_address": ocr_addr,
            "ocr_other": ocr_other,
            "log_line": log_line,
            "raw_response": response,
        }
        self.frame_evidence.append(evidence_entry)

        logger.info(
            f"  [Frame {frame_idx}/{total_frames}] ({temporal_zone.upper()}) -> "
            f"Tên OCR: {ocr_name} | Địa chỉ OCR: {ocr_addr} | Chữ khác: {ocr_other}"
        )
        return evidence_entry

    # =========================================================================
    # BƯỚC 2: BẦU CHỌN MAJORITY VOTING & KẾT LUẬN (conclude + Fast-Path)
    # =========================================================================
    def _select_best_ocr_candidate(
        self_or_cls,
        *args,
        **kwargs
    ) -> Any:
        """
        Bầu chọn (Majority Voting + Quality Scoring) ứng viên tốt nhất từ các frames.
        Hỗ trợ:
        1. Instance method: self._select_best_ocr_candidate("tên_quán") -> (best_val, frame_source_str)
        2. Static/Direct helper: Vintern1BExtractor._select_best_ocr_candidate(evidence_list, "tên_quán") -> best_val
        """
        evidence_list = []
        field = "tên_quán"
        is_direct_list_call = False

        if isinstance(self_or_cls, list):
            evidence_list = self_or_cls
            field = args[0] if len(args) > 0 else "tên_quán"
            is_direct_list_call = True
        elif hasattr(self_or_cls, "frame_evidence"):
            evidence_list = self_or_cls.frame_evidence
            if len(args) == 1:
                if isinstance(args[0], list):
                    evidence_list = args[0]
                    is_direct_list_call = True
                else:
                    field = args[0]
            elif len(args) >= 2:
                if isinstance(args[0], list):
                    evidence_list = args[0]
                    field = args[1]
                    is_direct_list_call = True
                else:
                    field = args[0]
                    evidence_list = args[1]
        elif len(args) >= 1 and isinstance(args[0], list):
            evidence_list = args[0]
            field = args[1] if len(args) > 1 else "tên_quán"
            is_direct_list_call = True

        candidates = []
        for e in evidence_list:
            val = e.get(field)
            if val:
                f_idx = e.get("frame_idx", 1)
                zone = e.get("temporal_zone", "body")
                candidates.append((val, f_idx, zone))

        if not candidates:
            return (None, None) if not is_direct_list_call else None

        # Nhóm các ứng viên tương đồng (không phân biệt hoa thường)
        norm_counts = Counter(c[0].lower().strip() for c in candidates)

        def score_candidate(item):
            val, f_idx, zone = item
            v_low = val.lower().strip()
            freq = norm_counts[v_low]
            score = freq * 10.0

            # Cộng điểm vùng thời gian: Nếu frame thuộc vùng outro hoặc intro (+4 điểm)
            if zone in ["outro", "intro"]:
                score += 4.0

            if field == "địa_chỉ":
                # Ưu tiên địa chỉ có số nhà và tên đường/quận rõ ràng
                if re.search(r'\d+', val):
                    score += 8.0
                if any(kw in v_low for kw in [
                    "phố", "đường", "ngõ", "hẻm", "quận", "phường", "khu", "tp",
                    "hà nội", "phú nhuận", "ba đình", "đống đa", "long biên", "bắc ninh", "hồ chí minh", "sài gòn"
                ]):
                    score += 6.0
                score += min(len(val), 45) * 0.15
            elif field == "tên_quán":
                # Ưu tiên tên quán có độ dài vừa phải (2 - 6 từ)
                word_cnt = len(val.split())
                if 2 <= word_cnt <= 6:
                    score += 6.0
                if any(kw in v_low for kw in ["quán", "tiệm", "nhà hàng", "ốc", "bún", "phở", "lẩu", "nướng", "cafe", "bánh"]):
                    score += 3.0
                score += min(len(val), 30) * 0.1
            return score

        best_val, best_frame, _ = max(candidates, key=score_candidate)
        if is_direct_list_call:
            return best_val

        # Liệt kê tất cả các frames có chứa best_val
        matched_frames = sorted(list({
            c[1] for c in candidates if c[0].lower().strip() == best_val.lower().strip()
        }))
        if len(matched_frames) == 1:
            frame_source_str = f"Frame {matched_frames[0]} (OCR)"
        else:
            frame_source_str = f"{', '.join([f'Frame {idx}' for idx in matched_frames])} (OCR)"

        return best_val, frame_source_str

    def _is_grounded_in_frames(self, val: Optional[str], field: str) -> bool:
        """
        Kiểm tra giá trị trích xuất từ LLM có căn cứ thực sự xuất hiện trên các khung hình không.
        Ngăn chặn triệt để hiện tượng LLM chép lại ví dụ trong Prompt.
        """
        if not val or val.strip().lower() in {"none", "null", "chưa có", "không có"}:
            return False
        val_clean = val.lower().strip()

        evidence_texts = []
        for e in self.frame_evidence:
            v_field = e.get(field)
            if v_field and isinstance(v_field, str):
                evidence_texts.append(v_field.lower().strip())
            other = e.get("đặc_trưng") or e.get("ocr_other")
            if other and isinstance(other, str):
                evidence_texts.append(other.lower().strip())

        if not evidence_texts:
            return False

        full_corpus = " ".join(evidence_texts)
        if val_clean in full_corpus:
            return True

        # Tách từ và kiểm tra tỷ lệ từ khóa (tối thiểu 50% các từ của val phải có trong frame evidence)
        words = [w for w in re.split(r'[\s,\.\-]+', val_clean) if len(w) >= 2]
        if not words:
            return False
        matched = [w for w in words if w in full_corpus]
        return (len(matched) / len(words)) >= 0.5

    def conclude(self) -> Dict[str, Any]:
        """
        BƯỚC 2: Bầu chọn Majority Voting & Kết luận cuối cùng (Pure Vision v3.0).
        - 1. Chạy _select_best_ocr_candidate cho tên quán và địa chỉ.
        - 2. Cơ chế Fast-Path: Nếu chỉ có <= 1 ứng viên duy nhất, trả về trực tiếp,
             không gọi thêm lượt LLM tổng hợp để tiết kiệm 1.5s và loại bỏ hiện tượng tự xóa chữ.
        - 3. Deterministic Grounding: Nếu gọi LLM mà kết quả bị mất số nhà, tự động phục hồi từ OCR.
        """
        # 1. Bầu chọn ứng viên OCR biển hiệu tốt nhất từ các frames
        best_ocr_name, ocr_name_src = self._select_best_ocr_candidate("tên_quán")
        best_ocr_addr, ocr_addr_src = self._select_best_ocr_candidate("địa_chỉ")

        # Thu thập các ứng viên hợp lệ duy nhất qua các frames
        valid_names = list({e["tên_quán"].strip() for e in self.frame_evidence if e.get("tên_quán")})
        valid_addrs = list({e["địa_chỉ"].strip() for e in self.frame_evidence if e.get("địa_chỉ")})

        # 2. Cơ chế Fast-Path:
        # Nếu chỉ có <= 1 ứng viên tên quán và <= 1 ứng viên địa chỉ duy nhất trên toàn bộ
        # các frame, trả về trực tiếp mà KHÔNG cần gọi thêm lượt suy luận LLM tổng hợp!
        if len(valid_names) <= 1 and len(valid_addrs) <= 1:
            pred_name = best_ocr_name
            pred_addr = best_ocr_addr
            logger.info(f"⚡ [Fast-Path kích hoạt]: Bỏ qua LLM tổng hợp -> Tên: {pred_name} | Địa chỉ: {pred_addr}")
        else:
            # Nếu có nhiều ứng viên khác biệt cần hợp nhất
            valid_frames_info = []
            for e in self.frame_evidence:
                parts = []
                if e.get("tên_quán"):
                    parts.append(f"Tên quán='{e['tên_quán']}'")
                if e.get("địa_chỉ"):
                    parts.append(f"Địa chỉ='{e['địa_chỉ']}'")
                if e.get("đặc_trưng"):
                    parts.append(f"Chữ khác='{e['đặc_trưng']}'")
                if parts:
                    valid_frames_info.append(f"- Frame {e['frame_idx']}: " + ", ".join(parts))

            frames_text = "\n".join(valid_frames_info) if valid_frames_info else "Không có chữ trên ảnh."

            prompt = build_step3_conclude_prompt(
                frames_text=frames_text,
                best_ocr_name=best_ocr_name,
                best_ocr_addr=best_ocr_addr,
            )

            pred_name = best_ocr_name
            pred_addr = best_ocr_addr

            if self.model is not None and self.tokenizer is not None:
                import torch
                with torch.no_grad():
                    response, _ = self.model.chat(
                        self.tokenizer,
                        pixel_values=None,
                        question=prompt,
                        generation_config=self.gen_config,
                        history=None,
                        return_history=True,
                    )
                parsed = parse_json_output(response)
                llm_name = clean_extracted_value(parsed.get("tên_quán"), field_type="name")
                llm_addr = clean_extracted_value(parsed.get("địa_chỉ"), field_type="address")

                # Hậu kiểm Quyết định Cuối cùng (Deterministic Grounding)
                if llm_name:
                    if self._is_grounded_in_frames(llm_name, "tên_quán"):
                        pred_name = llm_name
                    else:
                        logger.warning(f"⚠️ Bỏ qua tên quán ảo giác từ LLM (không có trong OCR): '{llm_name}', giữ '{best_ocr_name}'")
                        pred_name = best_ocr_name

                if llm_addr:
                    if self._is_grounded_in_frames(llm_addr, "địa_chỉ"):
                        if best_ocr_addr and re.search(r'\d+', best_ocr_addr) and not re.search(r'\d+', llm_addr):
                            pred_addr = best_ocr_addr
                        else:
                            pred_addr = llm_addr
                    else:
                        logger.warning(f"⚠️ Bỏ qua địa chỉ ảo giác từ LLM (không có trong OCR): '{llm_addr}', giữ '{best_ocr_addr}'")
                        pred_addr = best_ocr_addr

        # RÀNG BUỘC CỐT LÕI PURE VISION:
        # 1. Nếu không có bất kỳ frame nào đọc được địa chỉ (valid_addrs rỗng), hoặc không có nguồn dẫn chứng,
        #    thì tuyệt đối KHÔNG cho phép tồn tại địa chỉ (pred_addr = None).
        if not valid_addrs or not best_ocr_addr or not ocr_addr_src:
            pred_addr = None
            addr_source = None
        else:
            addr_source = ocr_addr_src

        # 2. Tương tự cho tên quán: nếu không có frame nào đọc được, thì pred_name = None
        if not valid_names or not best_ocr_name or not ocr_name_src:
            pred_name = None
            name_source = None
        else:
            name_source = ocr_name_src

        # Đánh giá độ tin cậy
        if pred_name and pred_addr:
            confidence = "Cao"
        elif pred_name or pred_addr:
            confidence = "Trung bình"
        else:
            confidence = "Thấp"

        final_result = {
            "tên_quán": pred_name,
            "địa_chỉ": pred_addr,
            "độ_tin_cậy": confidence,
            "dẫn_chứng": {
                "nguồn_tên_quán": name_source,
                "nguồn_địa_chỉ": addr_source,
                "name_source": name_source,
                "address_source": addr_source,
            },
            "confidence_status": confidence,
            "evidence": {
                "name_source": name_source,
                "address_source": addr_source,
            },
            "chi_tiết_frames": [
                {
                    "frame_idx": e.get("frame_idx"),
                    "temporal_zone": e.get("temporal_zone", "body"),
                    "timestamp_sec": e.get("timestamp_sec", 0.0),
                    "final_score": e.get("final_score", 0.0),
                    "tên_quán_ocr": e.get("tên_quán"),
                    "địa_chỉ_ocr": e.get("địa_chỉ"),
                    "chữ_khác_ocr": e.get("đặc_trưng"),
                    "ocr_name": e.get("tên_quán"),
                    "ocr_address": e.get("địa_chỉ"),
                    "ocr_other": e.get("đặc_trưng"),
                    "log_line": e.get("log_line"),
                }
                for e in self.frame_evidence
            ],
            "log_detect": "\n".join([e.get("log_line", "") for e in self.frame_evidence if e.get("log_line")]),
        }

        logger.info("=" * 50)
        logger.info("🎯 KẾT LUẬN CUỐI CÙNG (PURE VISION V3.0):")
        logger.info(f"  • Tên quán   : {pred_name}")
        logger.info(f"  • Địa chỉ    : {pred_addr}")
        logger.info(f"  • Độ tin cậy : {confidence}")
        logger.info(f"  • Dẫn chứng  : {final_result.get('evidence')}")
        logger.info("=" * 50)

        return final_result

    # =========================================================================
    # BƯỚC 3: DỌN DẸP BỘ NHỚ & RESET CONTEXT (clear_context)
    # =========================================================================
    def clear_context(self):
        """BƯỚC 3: Xóa sạch ngữ cảnh và giải phóng VRAM GPU."""
        self.current_context = None
        self.frame_evidence = []
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        logger.info("[✓] Đã xóa sạch ngữ cảnh & dọn dẹp bộ nhớ GPU.\n")

    # =========================================================================
    # WRAPPER PURE VISION CHO 1 VIDEO (analyze_frames)
    # =========================================================================
    def analyze_frames(
        self,
        frames: List[Union[Image.Image, np.ndarray, str]],
        candidates_meta: Optional[List[Any]] = None,
        video_id: Optional[str] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        Quy trình chuẩn Pure Vision 3 bước cho 1 video:
        1. Quét OCR tuần tự từng frame sạch (process_frame).
        2. Bầu chọn Majority Voting & Fast-Path tổng hợp (conclude).
        3. Dọn dẹp bộ nhớ GPU (clear_context).
        """
        self.frame_evidence = []
        total = len(frames)
        if verbose:
            logger.info(f"\n[VINTERN-1B PURE VISION] Xử lý {total} khung hình sạch cho video: {video_id or 'Unknown'}")
        try:
            for i, frame in enumerate(frames):
                meta = candidates_meta[i] if candidates_meta and i < len(candidates_meta) else None
                self.process_frame(frame, frame_idx=i + 1, total_frames=total, candidate_meta=meta)
            res = self.conclude()
            return res
        finally:
            self.clear_context()

    # =========================================================================
    # CÁC PHƯƠNG THỨC TƯƠNG THÍCH NGƯỢC
    # =========================================================================
    def init_video_context(
        self,
        script: str = "",
        comments: Optional[Union[str, List[str]]] = None,
        video_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Wrapper tương thích ngược không còn dùng trong v3.0."""
        self.current_context = {
            "video_id": video_id,
            "script": script,
            "preliminary_clues": {},
        }
        return self.current_context

    def analyze_video(
        self,
        frames: List[Union[Image.Image, np.ndarray, str]],
        script: str = "",
        comments: Optional[Union[str, List[str]]] = None,
        video_id: Optional[str] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Wrapper tương thích ngược chuyển tiếp sang analyze_frames."""
        return self.analyze_frames(frames=frames, video_id=video_id, verbose=verbose)

    def extract(
        self,
        frames: List[Union[Image.Image, np.ndarray]],
        script: str = "",
        video_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Wrapper tương thích ngược cho extract()."""
        res = self.analyze_frames(frames=frames, video_id=video_id, verbose=False)
        evidence = res.get("evidence", {})
        return {
            "tên_quán": res.get("tên_quán"),
            "địa_chỉ": res.get("địa_chỉ"),
            "nguồn_tên_quán": evidence.get("name_source"),
            "nguồn_địa_chỉ": evidence.get("address_source"),
            "log_detect": res.get("log_detect", ""),
            "confidence_status": res.get("confidence_status", "UNKNOWN"),
            "evidence": evidence,
            "chi_tiết_frames": res.get("chi_tiết_frames", []),
            "raw_output": json.dumps(res, ensure_ascii=False),
        }
