"""
Module logger: Cung cấp cấu hình logging chuẩn hóa cho toàn bộ dự án.
"""

import logging
import sys

# Tự động cấu hình stdout/stderr sang UTF-8 trên Windows nếu có thể
for stream in [sys.stdout, sys.stderr]:
    if hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def get_logger(name: str = "RestaurantExtractor", level: int = logging.INFO) -> logging.Logger:
    """
    Khởi tạo hoặc lấy logger chuẩn hóa với định dạng đẹp mắt và hỗ trợ Unicode UTF-8.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger

