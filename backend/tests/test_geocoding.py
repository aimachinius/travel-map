import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

from app.services.geocoding_service import ArcGISGeocoder


def test_generate_sub_queries_abbreviations():
    # Test tp. hcm, q., p., đ.
    raw = "34 đ. ngọc khánh, q. ba đình, hn"
    queries = ArcGISGeocoder.generate_sub_queries(raw)

    assert len(queries) > 0
    # Kiểm tra viết tắt được chuyển đổi
    combined = " ".join(queries).lower()
    assert "đường ngọc khánh" in combined
    assert "quận ba đình" in combined
    assert "hà nội" in combined


def test_generate_sub_queries_house_number_optimization():
    raw = "120 Lê Lợi, Phường Bến Thành, Quận 1, TPHCM"
    queries = ArcGISGeocoder.generate_sub_queries(raw)

    assert len(queries) >= 2
    # Query đầu tiên được chèn tiền tố "Đường"
    assert queries[0].startswith("120 Đường Lê Lợi")
    assert "Hồ Chí Minh" in queries[0]


def test_extract_house_number():
    assert ArcGISGeocoder.extract_house_number("34 Ngọc Khánh") == "34"
    assert ArcGISGeocoder.extract_house_number("12/4A Nguyễn Trãi") == "12/4A"
    assert ArcGISGeocoder.extract_house_number("Nguyễn Huệ") is None


@pytest.mark.asyncio
async def test_geocode_address_house_number_priority():
    mock_candidates = [
        {
            "address": "Lê Lợi, Bến Thành, Quận 1",
            "score": 95,
            "location": {"x": 106.69, "y": 10.77},
            "attributes": {"AddNum": "", "Score": 95, "Match_addr": "Lê Lợi, Quận 1"},
        },
        {
            "address": "45 Lê Lợi, Bến Thành, Quận 1",
            "score": 85,
            "location": {"x": 106.701, "y": 10.775},
            "attributes": {"AddNum": "45", "Score": 85, "Match_addr": "45 Lê Lợi, Quận 1"},
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"candidates": mock_candidates}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_resp

    lat, lon, norm_addr = await ArcGISGeocoder.geocode_address("45 Lê Lợi, Quận 1, TPHCM", client=mock_client)

    # Phải ưu tiên chọn candidate khớp số nhà 45
    assert lat == 10.775
    assert lon == 106.701
    assert "45 Lê Lợi" in norm_addr


@pytest.mark.asyncio
async def test_geocode_address_score_priority_when_no_house_number():
    mock_candidates = [
        {
            "address": "Chợ Bến Thành, Quận 1",
            "score": 90,
            "location": {"x": 106.698, "y": 10.772},
            "attributes": {"AddNum": "", "Score": 90, "Match_addr": "Chợ Bến Thành, Quận 1"},
        },
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"candidates": mock_candidates}

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_resp

    lat, lon, norm_addr = await ArcGISGeocoder.geocode_address("Chợ Bến Thành", client=mock_client)
    assert lat == 10.772
    assert lon == 106.698
    assert norm_addr == "Chợ Bến Thành, Quận 1"
