"""Standalone CLI Runner for Location-based Video Discovery Pipeline.

Allows testing address resolution, district coverage, keyword generation,
24h deduplication, and TikTok crawling.

Usage:
    python -m app.services.discovery_runner --lat 16.0738 --lon 108.1499 --radius 1500
"""

import argparse
import asyncio
import logging
import sys
from uuid import UUID

from app.db.session import SessionLocal
from app.services.discovery_service import DiscoveryService

# Configure logging with clear, readable format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("discovery_runner")


async def mock_enqueue_callback(run_id: UUID, priority: int) -> None:
    """Mock callback simulating Redis queue task dispatch."""
    logger.info(f"   >>> [REDIS DISPATCH MOCK] Đã đẩy task AnalysisRun({run_id}) vào hàng đợi ưu tiên {priority} (queue:low_priority).")


async def main():
    parser = argparse.ArgumentParser(
        description="Chạy thử nghiệm tiến trình Discovery Pipeline (Cào video ẩm thực theo vị trí)"
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=16.0738,
        help="Vĩ độ (Latitude), mặc định: 16.0738 (Hòa Khánh Nam, Liên Chiểu)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=108.1499,
        help="Kinh độ (Longitude), mặc định: 108.1499 (Hòa Khánh Nam, Liên Chiểu)",
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=1500.0,
        help="Bán kính quét theo mét (mặc định: 1500m)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bỏ qua kiểm tra chống quét lặp 24h",
    )

    args = parser.parse_args()

    db = SessionLocal()
    try:
        logger.info(f"Khởi tạo phiên chạy thử Discovery Runner với tọa độ ({args.lat}, {args.lon}), bán kính {args.radius}m...")
        runs = await DiscoveryService.discover_location(
            db=db,
            lat=args.lat,
            lon=args.lon,
            radius_m=args.radius,
            enqueue_callback=mock_enqueue_callback,
            force=args.force,
        )
        logger.info(f"\n[KẾT QUẢ CUỐI CÙNG] Đã tạo thành công {len(runs)} AnalysisRuns cho điểm quét.")
    except Exception as e:
        logger.error(f"[LỖI XẢY RA] {e}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

