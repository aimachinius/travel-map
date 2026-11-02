"""
Module main: CLI Entrypoint duy nhất cho toàn bộ hệ thống trích xuất thông tin quán ăn.
Hỗ trợ 3 chế độ:
1. single: Xử lý 1 video duy nhất (với kịch bản truyền vào).
2. batch: Xử lý hàng loạt theo danh sách từ CSV.
3. select_frames: Chỉ chạy module tiền xử lý thị giác (PySceneDetect + DBNet ONNX) để trích chọn keyframe.
"""

import os
import sys
import argparse
import json

# Đảm bảo import được src khi chạy trực tiếp `python src/main.py`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import PipelineConfig
from src.detectors.frame_selector import TextKeyframeSelector
from src.pipeline.restaurant_pipeline import RestaurantExtractorPipeline
from src.batch.batch_processor import BatchProcessor
from src.utils.logger import get_logger

logger = get_logger("MainCLI")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Hệ thống Trích xuất Thông tin Quán ăn từ Video & Kịch bản (PySceneDetect + DBNet + Vintern-1B)"
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="batch",
        choices=["single", "batch", "select_frames"],
        help="Chế độ thực thi: 'single' (1 video), 'batch' (nhiều video từ CSV), 'select_frames' (chỉ chọn keyframes)",
    )

    # Tham số cho chế độ single & select_frames
    parser.add_argument("--video", type=str, default=None, help="Đường dẫn đến file video cần xử lý")
    parser.add_argument("--script", type=str, default="", help="Nội dung kịch bản / audio transcript của video")
    parser.add_argument("--video_id", type=str, default=None, help="ID của video (mặc định lấy theo tên file)")

    # Tham số cho chế độ batch
    parser.add_argument("--csv", type=str, default=None, help="Đường dẫn file CSV chứa danh sách video_id & kịch bản")
    parser.add_argument("--videos_dir", type=str, default=None, help="Thư mục chứa các file video mp4")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số lượng video xử lý trong batch")
    parser.add_argument(
        "--start_index", "--start-index", "--start",
        type=int,
        default=0,
        help="Vị trí index bắt đầu trong file CSV (0-based, ví dụ: 40, mặc định: 0)",
    )
    parser.add_argument(
        "--start_video_id", "--start-video-id", "--start_vid",
        type=str,
        default=None,
        help="ID của video bắt đầu trong file CSV (chạy từ video này trở đi)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Tự động tiếp tục từ video kế tiếp sau video cuối cùng đã hoàn thành trong batch_results.csv",
    )
    parser.add_argument("--force", action="store_true", help="Không bỏ qua các video đã được xử lý trước đó")
    parser.add_argument(
        "--save_interval",
        type=int,
        default=10,
        help="Lưu định kỳ kết quả CSV và JSON sau mỗi N mẫu (mặc định: 10)",
    )

    # Cấu hình tiền xử lý & mô hình
    parser.add_argument("--output_dir", type=str, default=None, help="Thư mục lưu kết quả xuất ra")
    parser.add_argument("--top_k", type=int, default=5, help="Số lượng keyframe văn bản chọn tối đa cho mỗi video")
    parser.add_argument(
        "--sort_by",
        type=str,
        default="composite",
        choices=["composite", "area_ratio", "avg_score", "box_count"],
        help="Tiêu chí xếp hạng keyframe",
    )
    parser.add_argument("--threshold", type=float, default=27.0, help="Ngưỡng phát hiện chuyển cảnh PySceneDetect")
    parser.add_argument("--min_scene_len", type=int, default=15, help="Độ dài tối thiểu của một phân cảnh (frame)")
    parser.add_argument("--vlm_model", type=str, default="5CD-AI/Vintern-1B-v3_5", help="Tên mô hình Vintern-1B trên Hugging Face")
    parser.add_argument("--device", type=str, default=None, help="Thiết bị thực thi VLM ('cuda' hoặc 'cpu')")

    return parser.parse_args()


def main():
    args = parse_args()

    # Khởi tạo cấu hình dựa trên tham số dòng lệnh
    config = PipelineConfig(
        top_k_frames=args.top_k,
        sort_by=args.sort_by,
        scene_threshold=args.threshold,
        min_scene_len=args.min_scene_len,
        vlm_model_id=args.vlm_model,
        vlm_device=args.device,
    )
    if args.output_dir:
        config.default_output_dir = args.output_dir
    if args.csv:
        config.default_csv_path = args.csv
    if args.videos_dir:
        config.default_videos_dir = args.videos_dir

    # 1. Chế độ SELECT_FRAMES (Chỉ chạy tiền xử lý thị giác)
    if args.mode == "select_frames":
        if not args.video:
            logger.error("Chế độ 'select_frames' yêu cầu truyền vào tham số --video.")
            sys.exit(1)

        logger.info(f"Đang chạy trích chọn Keyframe cho video: {args.video}")
        selector = TextKeyframeSelector()
        select_out = selector.select_keyframes(
            video_path=args.video,
            top_k=config.top_k_frames,
            sort_by=config.sort_by,
            min_score=config.min_text_score,
            min_area_ratio=config.min_text_area_ratio,
            keep_frames_in_memory=True,
        )
        if isinstance(select_out, tuple) and len(select_out) >= 1 and isinstance(select_out[0], list):
            candidates = select_out[0]
        else:
            candidates = select_out

        out_dir = config.default_output_dir
        vid = args.video_id or os.path.splitext(os.path.basename(args.video))[0]
        saved_count = selector.export_drawn_frames(candidates, out_dir, vid)
        logger.info(f"Đã chọn {len(candidates)} keyframes | Lưu {saved_count} ảnh visualization tại: {out_dir}/{vid}")
        return

    # 2. Chế độ SINGLE (Xử lý 1 video duy nhất với VLM)
    if args.mode == "single":
        if not args.video:
            logger.error("Chế độ 'single' yêu cầu truyền vào tham số --video.")
            sys.exit(1)

        pipeline = RestaurantExtractorPipeline(config=config)
        result = pipeline.process_video(
            video_path=args.video,
            script=args.script,
            video_id=args.video_id,
        )
        print("\n" + "=" * 50)
        print("KẾT QUẢ TRÍCH XUẤT:")
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        print("=" * 50 + "\n")
        return

    # 3. Chế độ BATCH (Xử lý danh sách video từ CSV)
    if args.mode == "batch":
        batch_processor = BatchProcessor(config=config)
        batch_processor.process_from_csv(
            csv_path=config.default_csv_path,
            videos_dir=config.default_videos_dir,
            output_dir=config.default_output_dir,
            video_id_filter=args.video_id,
            limit=args.limit,
            start_index=args.start_index,
            start_video_id=args.start_video_id,
            resume=args.resume,
            skip_existing=not args.force,
            save_interval=args.save_interval,
        )


if __name__ == "__main__":
    main()
