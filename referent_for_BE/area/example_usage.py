"""Example script demonstrating usage of DistrictCoverageService and resolve_current_address."""

from .service import (
    OSM_ATTRIBUTION,
    DistrictCoverageItem,
    DistrictCoverageRequest,
    DistrictCoverageService,
    get_district_coverage,
    resolve_current_address,
)


def demo_current_address():
    print("=" * 70)
    print("1. Tra cứu địa chỉ vị trí hiện tại từ cấp Phường/Xã")
    print("=" * 70)
    lat, lon = 16.0704, 108.1618
    addr = resolve_current_address(lat, lon)
    print(f"Tọa độ                  : {lat}, {lon}")
    print(f"Địa chỉ từ cấp Phường/Xã: {addr['address_from_ward']}")
    if addr.get("road"):
        print(f"Đường/Phố               : {addr['road']}")
        print(f"Địa chỉ chi tiết đầy đủ : {addr['full_address']}")


def demo_hanoi_districts():
    print("\n" + "=" * 70)
    print("2. Tính toán ranh giới các Quận giao cắt quanh ĐH Bách Khoa Hà Nội")
    print("=" * 70)
    lat, lon = 21.0056, 105.8433
    radius_m = 1500

    print(f"Tâm: ({lat}, {lon}) | Bán kính: {radius_m}m | admin_level: 6 (Quận/Huyện)")
    try:
        items = get_district_coverage(lat=lat, lon=lon, radius_m=radius_m, admin_level="6")
        for idx, item in enumerate(items, 1):
            print(f" {idx}. {item['name']:<25}: {item['percentage']}% ({item['area_m2']:,} m²)")
    except Exception as e:
        print(f"Lỗi truy vấn: {e}")


def demo_typed_service():
    print("\n" + "=" * 70)
    print("3. Sử dụng Pydantic Model & Service: DistrictCoverageService")
    print("=" * 70)
    req = DistrictCoverageRequest(
        lat=10.7769,  # TP. Hồ Chí Minh
        lon=106.7009,
        radius_m=2000,
        admin_level="6",
    )
    print(f"Tâm: ({req.lat}, {req.lon}) | Bán kính: {req.radius_m}m")
    service = DistrictCoverageService()
    try:
        results = service.calculate_coverage(req)
        for idx, it in enumerate(results, 1):
            print(f" {idx}. {it.name:<25}: {it.percentage}% ({it.area_m2:,} m²)")
    except Exception as e:
        print(f"Lỗi truy vấn: {e}")

    print(f"\n{OSM_ATTRIBUTION}")


if __name__ == "__main__":
    demo_current_address()
    demo_hanoi_districts()
    demo_typed_service()

