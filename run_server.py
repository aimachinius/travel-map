"""
Script run_server.py: Điểm khởi chạy CLI chính thức cho AI Server.
Hỗ trợ cờ dòng lệnh linh hoạt cho Google Colab và Local:
  --port 8000
  --tunnel [cloudflare|ngrok|none]
  --low-vram
"""

import os
import sys
import argparse
import uvicorn

# Đảm bảo import được src khi chạy trực tiếp `python src/run_server.py`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import ServerConfig
from src.server.dependencies import set_server_config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Khởi chạy Restaurant Extraction AI Server v3.0 (FastAPI + Pure Vision + DBNet ONNX GPU + Vintern-1B)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Địa chỉ IP lắng nghe (mặc định '0.0.0.0' để nhận kết nối từ mọi card mạng)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Cổng kết nối nội bộ (mặc định: 8000)",
    )
    parser.add_argument(
        "--tunnel",
        type=str,
        default="cloudflare",
        choices=["cloudflare", "ngrok", "none"],
        help="Loại cầu nối ra Internet công khai (mặc định: 'cloudflare' cho Colab, chọn 'none' khi chỉ test local)",
    )
    parser.add_argument(
        "--low-vram",
        action="store_true",
        help="Bắt buộc kích hoạt chế độ Low-VRAM (phù hợp GPU 8GB như RTX 4060, RTX 3070)",
    )
    parser.add_argument(
        "--keep-raw-video",
        action="store_true",
        help="Không xóa file video MP4 sau khi trích xuất keyframe xong",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Bật chế độ auto-reload khi phát triển mã nguồn",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Thiết lập cấu hình máy chủ
    config = ServerConfig(
        host=args.host,
        port=args.port,
        tunnel_provider=args.tunnel,
        low_vram_mode=args.low_vram,
        keep_raw_video=args.keep_raw_video,
    )
    set_server_config(config)

    print("\n" + "=" * 65)
    print("🚀 ĐANG KHỞI CHẠY AI SERVER TRÍCH XUẤT QUÁN ĂN...")
    print(f"🏠 Cổng Local: http://127.0.0.1:{args.port}")
    print(f"🌐 Cầu nối   : {args.tunnel.upper()}")
    print(f"⚙️ Low-VRAM  : {'BẬT' if config.low_vram_mode else 'TẮT'}")
    print("=" * 65 + "\n")

    uvicorn.run(
        "src.server.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        access_log=True,
    )


if __name__ == "__main__":
    main()
