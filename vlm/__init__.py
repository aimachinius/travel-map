"""
Package vlm: Chứa các module tiền xử lý, text normalizer, prompt builder và wrapper Vintern-1B v2.
"""

from .preprocessor import build_transform, dynamic_preprocess
from .text_normalizer import (
    normalize_stt_text,
    clean_extracted_value,
    extract_regex_anchors,
    parse_json_output,
    validate_address_entities,
    HALLUCINATED_PHRASES,
)
from .prompt_builder import (
    build_step1_context_prompt,
    build_step2_ocr_prompt,
    build_step3_conclude_prompt,
    build_prompt,
)
from .vintern_extractor import Vintern1BExtractor

__all__ = [
    "build_transform",
    "dynamic_preprocess",
    "normalize_stt_text",
    "clean_extracted_value",
    "extract_regex_anchors",
    "parse_json_output",
    "validate_address_entities",
    "HALLUCINATED_PHRASES",
    "build_step1_context_prompt",
    "build_step2_ocr_prompt",
    "build_step3_conclude_prompt",
    "build_prompt",
    "Vintern1BExtractor",
]
