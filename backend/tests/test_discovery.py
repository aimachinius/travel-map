import pytest
from app.services.discovery_service import DiscoveryService


def test_generate_keywords_full_info():
    geo_info = {
        "poi": "Đại học Bách Khoa",
        "street": "Đường Nguyễn Lương Bằng",
        "district": "Liên Chiểu",
        "city": "Đà Nẵng",
    }
    keywords = DiscoveryService.generate_keywords(geo_info)

    assert "quán ăn gần Đại học Bách Khoa" in keywords
    assert "quán ngon đường Nguyễn Lương Bằng" in keywords
    assert "ăn vặt Liên Chiểu" in keywords


def test_generate_keywords_fallback():
    geo_info = {}
    keywords = DiscoveryService.generate_keywords(geo_info)
    assert len(keywords) > 0
    assert "quán ăn ngon" in keywords
