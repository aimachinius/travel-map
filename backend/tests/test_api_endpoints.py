from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.analysis_run import AnalysisRun
from app.models.place import Place
from app.models.saved_place import SavedPlace
from app.models.saved_video import SavedVideo
from app.models.user import User
from app.models.video import Video


@pytest.fixture
def test_user():
    return User(
        id=uuid4(),
        username="tester",
        email="tester@example.com",
        password_hash="fakehash",
        is_active=True,
    )


@pytest.fixture
def auth_client(test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_submit_video_endpoint_returns_202(auth_client, test_user):
    fake_video = Video(
        id=uuid4(),
        platform="tiktok",
        platform_video_id="7123456789012345678",
        video_url="https://www.tiktok.com/@food/video/7123456789012345678",
        created_at=datetime.now(timezone.utc),
    )
    fake_run = AnalysisRun(
        id=uuid4(),
        user_id=test_user.id,
        video_id=fake_video.id,
        submitted_url=fake_video.video_url,
        status="PENDING",
        trigger_source="USER_SUBMIT",
        priority=1,
        created_at=datetime.now(timezone.utc),
    )

    with patch("app.api.v1.endpoints.videos.submit_video", new_callable=AsyncMock) as mock_submit:
        mock_submit.return_value = (fake_video, fake_run, False)

        resp = auth_client.post(
            "/api/v1/videos/submit",
            json={"video_url": "https://www.tiktok.com/@food/video/7123456789012345678"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["analysis_run_id"] == str(fake_run.id)
        assert data["video_id"] == str(fake_video.id)
        assert data["status"] == "PENDING"
        assert data["cached"] is False


def test_saved_places_endpoints(auth_client, test_user):
    place_id = uuid4()
    mock_saved = SavedPlace(id=uuid4(), user_id=test_user.id, place_id=place_id)

    # 1. POST /api/v1/saved/places/{place_id} -> 201 Created khi mới lưu
    with patch("app.api.v1.endpoints.saved.SavedService.save_place") as mock_save:
        mock_save.return_value = (mock_saved, True)
        resp1 = auth_client.post(f"/api/v1/saved/places/{place_id}")
        assert resp1.status_code == 201
        assert resp1.json()["status"] == "success"

        # POST idempotent -> 200 OK khi đã tồn tại
        mock_save.return_value = (mock_saved, False)
        resp2 = auth_client.post(f"/api/v1/saved/places/{place_id}")
        assert resp2.status_code == 200

    # 2. DELETE /api/v1/saved/places/{place_id} -> 204 No Content
    with patch("app.api.v1.endpoints.saved.SavedService.unsave_place") as mock_unsave:
        mock_unsave.return_value = True
        resp3 = auth_client.delete(f"/api/v1/saved/places/{place_id}")
        assert resp3.status_code == 204

        # DELETE lần 2 -> 404
        mock_unsave.return_value = False
        resp4 = auth_client.delete(f"/api/v1/saved/places/{place_id}")
        assert resp4.status_code == 404


def test_saved_videos_endpoints(auth_client, test_user):
    video_id = uuid4()
    mock_saved = SavedVideo(id=uuid4(), user_id=test_user.id, video_id=video_id)

    with patch("app.api.v1.endpoints.saved.SavedService.save_video") as mock_save:
        # Lần 1: 201
        mock_save.return_value = (mock_saved, True)
        resp1 = auth_client.post(f"/api/v1/saved/videos/{video_id}")
        assert resp1.status_code == 201

        # Lần 2: 200
        mock_save.return_value = (mock_saved, False)
        resp2 = auth_client.post(f"/api/v1/saved/videos/{video_id}")
        assert resp2.status_code == 200

    with patch("app.api.v1.endpoints.saved.SavedService.unsave_video") as mock_unsave:
        mock_unsave.return_value = True
        resp3 = auth_client.delete(f"/api/v1/saved/videos/{video_id}")
        assert resp3.status_code == 204


def test_places_nearby_and_search_endpoints(auth_client):
    with patch("app.api.v1.endpoints.places.PlaceService.get_nearby_videos") as mock_nearby:
        mock_nearby.return_value = [
            {
                "video": {
                    "id": str(uuid4()),
                    "platform": "tiktok",
                    "platform_video_id": "123",
                    "video_url": "https://tiktok.com/@food/video/123",
                    "title": "Bún chả",
                    "caption": None,
                    "duration_seconds": 60.0,
                    "thumbnail_url": None,
                    "author_name": "Reviewer",
                    "created_at": datetime.now(timezone.utc),
                    "is_saved": False,
                },
                "place": {
                    "id": str(uuid4()),
                    "name": "Bún chả Sinh Từ",
                    "address": "Nguyễn Khuyến",
                    "latitude": 21.02,
                    "longitude": 105.84,
                    "category": "Ăn uống",
                    "is_saved": False,
                },
                "match": {
                    "confidence_status": "HIGH",
                    "evidence_sources": ["audio", "vision"],
                },
                "distance_m": 450.5,
            }
        ]

        resp = auth_client.get("/api/v1/places/nearby-videos?lat=21.02&lon=105.84&radius_m=2000")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["place"]["name"] == "Bún chả Sinh Từ"
        assert data[0]["distance_m"] == 450.5
