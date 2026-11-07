"""Command-Line Interface for District Coverage and Administrative Area calculation."""

import argparse
import json
import pathlib
import sys
from typing import List

# Ensure current and package directories are on sys.path
_current_dir = pathlib.Path(__file__).resolve().parent
_find_dir = _current_dir.parent
_root_dir = _find_dir.parent
for p in (str(_root_dir), str(_find_dir), str(_current_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from .service import OSM_ATTRIBUTION, get_district_coverage, resolve_current_address
except ImportError:
    from service import OSM_ATTRIBUTION, get_district_coverage, resolve_current_address  # type: ignore


def main(argv: List[str] = None):
    parser = argparse.ArgumentParser(
        description="Calculate administrative district coverage percentage within radius_m from (lat, lon) with current address resolution."
    )
    parser.add_argument(
        "--lat",
        type=float,
        default=21.0056,
        help="Search latitude (-90 to 90). Default: 21.0056 (Hanoi Bách Khoa)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        default=105.8433,
        help="Search longitude (-180 to 180). Default: 105.8433 (Hanoi Bách Khoa)",
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=1500.0,
        help="Search radius in meters. Default: 1500m",
    )
    parser.add_argument(
        "--admin-level",
        type=str,
        default="6",
        help="Administrative level (default '6' for District, '4' for Province/City, '8' for Ward).",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help="Custom Overpass server endpoint (optional).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass local cache.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output raw JSON instead of formatted table.",
    )

    args = parser.parse_args(argv)

    # 1. First, resolve and display the current location address starting from ward level
    current_addr = resolve_current_address(
        lat=args.lat,
        lon=args.lon,
        use_cache=not args.no_cache,
    )

    if not args.as_json:
        print("=" * 80)
        print("VỊ TRÍ HIỆN TẠI (CURRENT LOCATION):")
        print(f"  Tọa độ (Coordinates)     : {args.lat}, {args.lon}")
        if current_addr.get("road"):
            print(f"  Tuyến đường (Street)     : {current_addr['road']}")
        print(f"  Địa chỉ (Từ cấp Phường)  : {current_addr['address_from_ward']}")
        if current_addr.get("full_address") and current_addr.get("road"):
            print(f"  Địa chỉ chi tiết đầy đủ  : {current_addr['full_address']}")
        print("=" * 80)

    # 2. Next, calculate the administrative coverage within the search radius
    servers = [args.endpoint] if args.endpoint else None

    print(
        f"\nĐang tính toán phạm vi bao phủ (admin_level={args.admin_level}) trong bán kính {args.radius}m quanh ({args.lat}, {args.lon})...",
        file=sys.stderr,
    )

    try:
        results = get_district_coverage(
            lat=args.lat,
            lon=args.lon,
            radius_m=args.radius,
            admin_level=args.admin_level,
            servers=servers,
            use_cache=not args.no_cache,
        )
    except Exception as e:
        print(f"Error during calculation: {e}", file=sys.stderr)
        sys.exit(1)

    if args.as_json:
        output_payload = {
            "current_location": current_addr,
            "query": {
                "lat": args.lat,
                "lon": args.lon,
                "radius_m": args.radius,
                "admin_level": args.admin_level,
            },
            "attribution": OSM_ATTRIBUTION,
            "districts_count": len(results),
            "results": results,
        }
        print(json.dumps(output_payload, ensure_ascii=False, indent=2))
        return

    print(f"\nFound {len(results)} intersecting administrative units (admin_level={args.admin_level}):")
    print("=" * 80)
    print(f"{'No.':<4} | {'District Name':<28} | {'OSM ID':<12} | {'Area (m²)':<14} | {'Coverage (%)':<12}")
    print("-" * 80)

    for idx, item in enumerate(results, 1):
        area_fmt = f"{item['area_m2']:,.1f}"
        pct_fmt = f"{item['percentage']:.2f}%"
        print(f"{idx:<4} | {item['name']:<28} | {item['osm_id']:<12} | {area_fmt:<14} | {pct_fmt:<12}")

    print("=" * 80)
    print(f"{OSM_ATTRIBUTION}")


if __name__ == "__main__":
    main()

