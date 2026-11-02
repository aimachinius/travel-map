"""
Script run_tests.py: CLI Test Runner tập trung cho toàn bộ hệ thống AI Server.
Cho phép chạy kiểm thử từng module độc lập hoặc toàn bộ hệ sinh thái:
  python src/tests/run_tests.py --module downloader
  python src/tests/run_tests.py --module stt
  python src/tests/run_tests.py --module vision
  python src/tests/run_tests.py --module vlm
  python src/tests/run_tests.py --module storage
  python src/tests/run_tests.py --module tunnel
  python src/tests/run_tests.py --module pipeline
  python src/tests/run_tests.py --module api
  python src/tests/run_tests.py --module all
"""

import sys
import os
import argparse
import unittest
import time

# Đảm bảo đường dẫn import được src
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

MODULE_MAPPING = {
    "downloader": "src.tests.test_downloader",
    "vision": "src.tests.test_vision_detector",
    "vlm": "src.tests.test_vlm_extractor",
    "storage": "src.tests.test_storage_manager",
    "tunnel": "src.tests.test_tunnel_manager",
    "pipeline": "src.tests.test_server_pipeline",
    "api": "src.tests.test_api_endpoints",
    "batch": "src.tests.test_batch_processor",
}


def run_tests_for_module(module_name: str) -> bool:
    print("\n" + "=" * 65)
    print(f"🧪 [BẮT ĐẦU KIỂM THỬ ĐỘC LẬP MODULE: {module_name.upper()}]")
    print("=" * 65)

    start_time = time.time()
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(MODULE_MAPPING[module_name])
    except Exception as e:
        print(f"❌ Không thể nạp module test '{MODULE_MAPPING[module_name]}': {e}")
        return False

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("-" * 65)
    status_str = "✅ THÀNH CÔNG (PASSED)" if result.wasSuccessful() else "❌ THẤT BÀI (FAILED)"
    print(f"Kết quả: {status_str} | Thời gian: {elapsed:.2f}s | Lỗi: {len(result.errors)} | Thất bại: {len(result.failures)}")
    print("=" * 65 + "\n")
    return result.wasSuccessful()


def main():
    parser = argparse.ArgumentParser(description="AI Server Independent Module Test Runner v3.0 (Pure Vision)")
    parser.add_argument(
        "--module",
        type=str,
        default="all",
        choices=["downloader", "vision", "vlm", "storage", "tunnel", "pipeline", "api", "batch", "all"],
        help="Chọn module độc lập cần kiểm thử (mặc định: 'all')",
    )
    args = parser.parse_args()

    if args.module == "all":
        print("\n" + "=" * 65)
        print("🚀 [CHẠY KIỂM THỬ TOÀN DIỆN TẤT CẢ CÁC MODULE TRONG HỆ THỐNG]")
        print("=" * 65)
        start_all = time.time()
        results = {}
        for mod in MODULE_MAPPING.keys():
            success = run_tests_for_module(mod)
            results[mod] = success

        total_elapsed = time.time() - start_all
        print("\n" + "=" * 65)
        print("📊 [TỔNG KẾT KẾT QUẢ KIỂM THỬ TOÀN HỆ THỐNG]")
        print("=" * 65)
        all_passed = True
        for mod, success in results.items():
            status_symbol = "✅ PASSED" if success else "❌ FAILED"
            print(f"  - Module {mod.ljust(12)}: {status_symbol}")
            if not success:
                all_passed = False

        print("-" * 65)
        print(f"Tổng thời gian: {total_elapsed:.2f}s | Trạng thái chung: {'✅ TẤT CẢ MODULE ĐẠT' if all_passed else '❌ CÓ MODULE THẤT BÀI'}")
        print("=" * 65 + "\n")
        sys.exit(0 if all_passed else 1)
    else:
        success = run_tests_for_module(args.module)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
