"""Unit and integration tests for Location-Based Video Discovery Pipeline.

Tests:
1. Haversine distance and bounding box calculations.
2. Administrative keyword generation strictly from ward/commune level up (no POIs/streets).
3. Orthogonal category distribution (food, cafe, snack).
4. 24-hour keyword deduplication.
5. 1km spatial caching threshold within 24 hours.
6. End-to-end DiscoveryService execution flow with mocked external network calls.
"""

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from geoalchemy2.elements import WKTElement

from app.models.analysis_run import AnalysisRun
from app.models.discovery_scan import DiscoveryScan
from app.models.video import Video
from app.services.area.distance import haversine_distance
from app.services.area.geometry import calculate_bbox
from app.services.discovery.keyword_generator import (
    clean_admin_name,
    generate_orthogonal_keywords,
)
from app.services.discovery_service import DiscoveryService


# =========================================================================
# 1. TESTS FOR DISTANCE & GEOMETRY
# =========================================================================

def test_haversine_distance():
    # Distance between BK Da Nang (16.0738, 108.1499) and Dragon Bridge (16.0610, 108.2208) ~ 7.7 km
    dist = haversine_distance(16.0738, 108.1499, 16.0610, 108.2208)
    assert 7400 < dist < 8000

    # Same point should have 0 distance
    assert haversine_distance(16.0, 108.0, 16.0, 108.0) == 0.0


def test_calculate_bbox():
    lat, lon, radius_m = 16.0738, 108.1499, 1000.0
    south, west, north, east = calculate_bbox(lat, lon, radius_m)

    assert south < lat < north
    assert west < lon < east
    assert round(north - south, 4) > 0


# =========================================================================
# 2. TESTS FOR ADMINISTRATIVE KEYWORD GENERATION (NO POIS / STREETS)
# =========================================================================

def test_clean_admin_name():
    assert clean_admin_name("Phường Hòa Khánh Nam") == "Hòa Khánh Nam"
    assert clean_admin_name("Quận Liên Chiểu") == "Liên Chiểu"
    assert clean_admin_name("Thành phố Đà Nẵng") == "Đà Nẵng"
    assert clean_admin_name("Tỉnh Quảng Nam") == "Quảng Nam"
    assert clean_admin_name("Xã Hòa Châu") == "Hòa Châu"
    # Preserves numbered units like Quận 1, Phường 3
    assert clean_admin_name("Quận 1") == "Quận 1"
    assert clean_admin_name("Phường 3") == "Phường 3"
    assert clean_admin_name("Phường 10") == "Phường 10"
    assert clean_admin_name(None) is None


def test_generate_orthogonal_keywords_strictly_administrative():
    current_address = {
        "lat": 16.0738,
        "lon": 108.1499,
        "ward": "Phường Hòa Khánh Nam",
        "district": "Quận Liên Chiểu",
        "city": "Thành phố Đà Nẵng",
        "country": "Việt Nam",
        "road": "Đường Nguyễn Lương Bằng",  # Should be IGNORED
        "poi": "Trường Đại học Bách Khoa",  # Should be IGNORED
    }
    coverage_items = [
        {"osm_id": 1, "name": "Quận Liên Chiểu", "percentage": 85.0},
        {"osm_id": 2, "name": "Quận Thanh Khê", "percentage": 15.0},
    ]

    keywords = generate_orthogonal_keywords(current_address, coverage_items, max_keywords=6)

    # 1. Assert NO POI or street name is in any generated keyword
    for kw in keywords:
        assert "Bách Khoa" not in kw
        assert "Nguyễn Lương Bằng" not in kw
        assert "trường" not in kw.lower()

    # 2. Assert administrative names (Hòa Khánh Nam, Liên Chiểu, Đà Nẵng) are used
    assert any("Hòa Khánh Nam" in kw for kw in keywords)

    # 3. Assert orthogonal categories exist (food, cafe, snacks)
    has_food = any("quán ăn ở" in kw for kw in keywords)
    has_cafe = any("quán cafe ở" in kw for kw in keywords)
    has_snack = any("ăn vặt" in kw for kw in keywords)

    assert has_food, "Must contain main food category"
    assert has_cafe, "Must contain cafe / drink category"
    assert has_snack, "Must contain snack category"


def test_generate_orthogonal_keywords_single_variant_per_category():
    current_address = {
        "ward": "Phường Hòa Khánh Bắc",
        "district": "Quận Liên Chiểu",
        "city": "Đà Nẵng",
    }
    keywords = generate_orthogonal_keywords(current_address, max_keywords=3)

    categories = [
        "quán ăn ở",
        "quán cafe ở",
        "ăn vặt",
    ]
    # Each category should appear at most once among the top 3
    for cat in categories:
        count = sum(1 for kw in keywords if kw.startswith(cat))
        assert count <= 1


# =========================================================================
# 3. TESTS FOR 24H KEYWORD DEDUPLICATION
# =========================================================================

def test_get_recent_crawled_keywords():
    mock_db = MagicMock()
    # Mock return of scalars().all() with lists of keywords from the last 24h
    mock_db.scalars.return_value.all.return_value = [
        ["quán ăn ở Hòa Khánh Đà Nẵng", "quán cafe ở Hòa Khánh Đà Nẵng"],
        ["ăn vặt Liên Chiểu Đà Nẵng"],
    ]

    recent_keywords = DiscoveryService.get_recent_crawled_keywords(mock_db, within_hours=24)

    assert "quán ăn ở hòa khánh đà nẵng" in recent_keywords
    assert "quán cafe ở hòa khánh đà nẵng" in recent_keywords
    assert "ăn vặt liên chiểu đà nẵng" in recent_keywords
    assert "quán bún chả" not in recent_keywords


# =========================================================================
# 4. TESTS FOR 1KM SPATIAL CACHING THRESHOLD
# =========================================================================

def test_is_area_recently_scanned_true():
    mock_db = MagicMock()
    mock_db.scalar.return_value = uuid.uuid4()  # Existing record found within 1km

    is_scanned = DiscoveryService.is_area_recently_scanned(
        mock_db, lat=16.0738, lon=108.1499, threshold_distance_m=1000.0, within_hours=24
    )
    assert is_scanned is True


def test_is_area_recently_scanned_false():
    mock_db = MagicMock()
    mock_db.scalar.return_value = None  # No record found

    is_scanned = DiscoveryService.is_area_recently_scanned(
        mock_db, lat=16.0738, lon=108.1499, threshold_distance_m=1000.0, within_hours=24
    )
    assert is_scanned is False


# =========================================================================
# 5. TESTS FOR FULL DISCOVERY SERVICE ORCHESTRATION
# =========================================================================

@pytest.mark.asyncio
async def test_discover_location_aborts_when_spatially_scanned_within_1km():
    mock_db = MagicMock()
    mock_db.scalar.return_value = uuid.uuid4()  # Simulated match within 1km

    runs = await DiscoveryService.discover_location(
        db=mock_db,
        lat=16.0738,
        lon=108.1499,
        radius_m=1500.0,
        force=False,
    )

    assert runs == []
    # Assert DB did not insert any new DiscoveryScan
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
async def test_discover_location_bypasses_check_with_force_true():
    mock_db = MagicMock()
    mock_db.scalar.return_value = uuid.uuid4()  # Simulated match within 1km
    mock_db.scalars.return_value.all.return_value = []

    with patch(
        "app.services.discovery_service.resolve_current_address",
        return_value={"ward": "Hòa Khánh Nam", "district": "Liên Chiểu", "city": "Đà Nẵng"},
    ), patch(
        "app.services.discovery_service.get_district_coverage",
        return_value=[],
    ), patch(
        "app.services.discovery_service.crawl_tiktok_links_async",
        new=AsyncMock(return_value=[]),
    ):
        runs = await DiscoveryService.discover_location(
            db=mock_db,
            lat=16.0738,
            lon=108.1499,
            radius_m=1500.0,
            force=True,  # Bypasses spatial check
        )

        # Should proceed past Step 0 and add DiscoveryScan
        assert mock_db.add.called


@pytest.mark.asyncio
async def test_discover_location_aborts_when_all_keywords_are_24h_duplicates():
    mock_db = MagicMock()
    # 1. Spatial check returns None (not scanned)
    mock_db.scalar.return_value = None

    # 2. Return recent keywords that match all generated keywords
    mock_db.scalars.return_value.all.return_value = [
        [
            "quán ăn ở hòa khánh nam đà nẵng",
            "quán cafe ở hòa khánh nam đà nẵng",
            "ăn vặt hòa khánh nam đà nẵng",
            "quán ăn ở liên chiểu đà nẵng",
            "quán cafe ở liên chiểu đà nẵng",
            "ăn vặt liên chiểu đà nẵng",
        ]
    ]

    with patch(
        "app.services.discovery_service.resolve_current_address",
        return_value={
            "ward": "Hòa Khánh Nam",
            "district": "Liên Chiểu",
            "city": "Đà Nẵng",
        },
    ), patch(
        "app.services.discovery_service.get_district_coverage",
        return_value=[],
    ), patch(
        "app.services.discovery_service.crawl_tiktok_links_async"
    ) as mock_crawl:
        runs = await DiscoveryService.discover_location(
            db=mock_db,
            lat=16.0738,
            lon=108.1499,
        )

        assert runs == []
        mock_crawl.assert_not_called()


@pytest.mark.asyncio
async def test_discover_location_successful_run():
    mock_db = MagicMock()
    # Spatial check returns None (not scanned)
    mock_db.scalar.return_value = None
    # No recent keywords in 24h
    mock_db.scalars.return_value.all.return_value = []

    mock_crawled_urls = [
        "https://www.tiktok.com/@user/video/7123456789012345678?is_from_webapp=1",
        "https://www.tiktok.com/@user/video/7123456789012345679",
    ]

    enqueue_called = []

    async def mock_enqueue(run_id, priority):
        enqueue_called.append((run_id, priority))

    with patch(
        "app.services.discovery_service.resolve_current_address",
        return_value={
            "ward": "Phường Hòa Khánh Nam",
            "district": "Quận Liên Chiểu",
            "city": "Thành phố Đà Nẵng",
            "full_address": "Phường Hòa Khánh Nam, Quận Liên Chiểu, Thành phố Đà Nẵng",
        },
    ), patch(
        "app.services.discovery_service.get_district_coverage",
        return_value=[{"name": "Quận Liên Chiểu", "percentage": 100.0}],
    ), patch(
        "app.services.discovery_service.crawl_tiktok_links_async",
        new=AsyncMock(return_value=mock_crawled_urls),
    ):
        runs = await DiscoveryService.discover_location(
            db=mock_db,
            lat=16.0738,
            lon=108.1499,
            radius_m=1500.0,
            enqueue_callback=mock_enqueue,
        )

        # Should create 2 AnalysisRuns
        assert len(runs) == 2
        for r in runs:
            assert r.priority == 2
            assert r.trigger_source == "SYSTEM_DISCOVERY"
            assert r.status == "PENDING"

        # Check enqueue callback was executed with priority=2
        assert len(enqueue_called) == 2
        for run_id, prio in enqueue_called:
            assert prio == 2

