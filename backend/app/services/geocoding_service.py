import logging
import re
from typing import Any
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ArcGISGeocoder:
    """
    ArcGIS World Geocoding Service integration.
    Only uses ArcGIS World Geocoding Service (VNM countryCode).
    """

    @classmethod
    def generate_sub_queries(cls, raw_address: str) -> list[str]:
        if not raw_address or not raw_address.strip():
            return []

        # 1. Chuyển các dấu gạch ngang " - " thành dấu phẩy ", "
        addr = re.sub(r"\s+-\s+", ", ", raw_address.strip())
        addr = re.sub(r"-\s+", ", ", addr)

        # 2. Áp dụng từ điển Regex mở rộng viết tắt tiếng Việt
        replacements = [
            (r"\btphcm\b", "Hồ Chí Minh"),
            (r"\btp\.?\s*hcm\b", "Hồ Chí Minh"),
            (r"\bhn\b", "Hà Nội"),
            (r"\btp\.\s*", "Thành phố "),
            (r"\bq\.\s*", "Quận "),
            (r"\bp\.\s*", "Phường "),
            (r"\btx\.\s*", "Thị xã "),
            (r"\btt\.\s*", "Thị trấn "),
            (r"\bđ\.\s*", "Đường "),
            (r"\bng\.\s*", "Ngõ "),
            (r"\bh\.\s*", "Huyện "),
            (r"\bquận\s+phú\b", "Quận Phú Nhuận"),
            (r"\bphú\s+nhuận\b", "Phú Nhuận"),
            (r"\bbình\s+thạnh\b", "Bình Thạnh"),
            (r"\bgò\s+vấp\b", "Gò Vấp"),
            (r"\btân\s+bình\b", "Tân Bình"),
            (r"\btân\s+phú\b", "Tân Phú"),
        ]

        normalized = addr
        for pattern, repl in replacements:
            normalized = re.sub(pattern, repl, normalized, flags=re.IGNORECASE)

        # Bóc tách số nhà ở đầu chuỗi (ví dụ: "34 Ngọc Khánh, Ba Đình, Hà Nội" -> house_num="34", rest="Ngọc Khánh, Ba Đình, Hà Nội")
        queries: list[str] = [normalized]

        match_house = re.match(r"^(\d+[a-zA-Z0-9\/\-]*)\s+([^,]+)(?:,\s*(.+))?$", normalized)
        if match_house:
            house_num = match_house.group(1)
            street = match_house.group(2).strip()
            rest = match_house.group(3).strip() if match_house.group(3) else ""

            # Thêm tiền tố "Đường" nếu chưa có
            if not re.match(r"^(đường|phố|ngõ|ngách|hẻm|đại lộ)\b", street, flags=re.IGNORECASE):
                optimized_street = f"Đường {street}"
            else:
                optimized_street = street

            if rest:
                query_with_street = f"{house_num} {optimized_street}, {rest}"
            else:
                query_with_street = f"{house_num} {optimized_street}"

            if query_with_street not in queries:
                queries.insert(0, query_with_street)

        return queries

    @classmethod
    def extract_house_number(cls, address: str) -> str | None:
        match = re.match(r"^(\d+[a-zA-Z0-9\/\-]*)", address.strip())
        return match.group(1) if match else None

    @classmethod
    async def geocode_address(
        cls,
        address: str,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[float | None, float | None, str | None]:
        """
        Gọi ArcGIS findAddressCandidates với countryCode=VNM, maxLocations=5.
        Luật chọn ứng viên:
        - Ưu tiên 1: AddNum hoặc Match_addr/LongLabel chứa chính xác số nhà mục tiêu.
        - Ưu tiên 2: Ứng viên đầu tiên có score >= 80.
        Trả về (latitude, longitude, normalized_address).
        """
        if not address or not address.strip():
            return None, None, None

        sub_queries = cls.generate_sub_queries(address)
        target_house_num = cls.extract_house_number(address)

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True

        try:
            for query in sub_queries:
                params = {
                    "f": "json",
                    "singleLine": query,
                    "countryCode": "VNM",
                    "maxLocations": 5,
                    "outFields": "AddNum,Match_addr,LongLabel,Score,Type,Addr_type",
                }

                try:
                    response = await client.get(settings.ARCGIS_GEOCODE_URL, params=params)
                    if response.status_code != 200:
                        logger.warning(f"ArcGIS geocode status {response.status_code} for query: {query}")
                        continue

                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue

                    # Ưu tiên 1: Có số nhà khớp chính xác
                    if target_house_num:
                        for cand in candidates:
                            attrs = cand.get("attributes", {})
                            add_num = str(attrs.get("AddNum") or "")
                            match_addr = str(cand.get("address") or attrs.get("Match_addr") or "")
                            long_label = str(attrs.get("LongLabel") or "")

                            house_pattern = re.compile(rf"\b{re.escape(target_house_num)}\b", re.IGNORECASE)
                            if (
                                add_num.lower() == target_house_num.lower()
                                or house_pattern.search(match_addr)
                                or house_pattern.search(long_label)
                            ):
                                loc = cand.get("location", {})
                                lat = loc.get("y")
                                lon = loc.get("x")
                                norm_addr = attrs.get("LongLabel") or attrs.get("Match_addr") or cand.get("address")
                                if lat is not None and lon is not None:
                                    logger.info(f"ArcGIS house number match for '{address}': lat={lat}, lon={lon}")
                                    return float(lat), float(lon), norm_addr

                    # Ưu tiên 2: Ứng viên đầu tiên có score >= 80
                    for cand in candidates:
                        score = cand.get("score", 0)
                        if score >= 80:
                            loc = cand.get("location", {})
                            lat = loc.get("y")
                            lon = loc.get("x")
                            attrs = cand.get("attributes", {})
                            norm_addr = attrs.get("LongLabel") or attrs.get("Match_addr") or cand.get("address")
                            if lat is not None and lon is not None:
                                logger.info(f"ArcGIS score >= 80 ({score}) match for '{address}': lat={lat}, lon={lon}")
                                return float(lat), float(lon), norm_addr

                except Exception as ex:
                    logger.warning(f"Error querying ArcGIS for query '{query}': {ex}")

            logger.warning(f"Could not geocode address: {address}")
            return None, None, None

        finally:
            if should_close:
                await client.aclose()

    @classmethod
    async def reverse_geocode(
        cls,
        lat: float,
        lon: float,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        """
        Gọi ArcGIS reverseGeocode với location=lon,lat và langCode="vi"
        để lấy tên đường / địa danh.
        """
        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True

        try:
            params = {
                "f": "json",
                "location": f"{lon},{lat}",
                "langCode": "vi",
            }
            response = await client.get(settings.ARCGIS_REVERSE_GEOCODE_URL, params=params)
            if response.status_code == 200:
                data = response.json()
                address_info = data.get("address", {})
                return {
                    "match_addr": address_info.get("Match_addr", ""),
                    "street": address_info.get("Address", "") or address_info.get("Street", ""),
                    "district": address_info.get("District", "") or address_info.get("Subregion", ""),
                    "city": address_info.get("City", ""),
                    "poi": address_info.get("PlaceName", "") or address_info.get("ShortLabel", ""),
                }
            return {}
        except Exception as e:
            logger.warning(f"Error calling ArcGIS reverseGeocode for ({lat}, {lon}): {e}")
            return {}
        finally:
            if should_close:
                await client.aclose()
