import json
import pytest
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.websocket_manager import ConnectionManager


@pytest.mark.asyncio
async def test_websocket_connect_and_disconnect():
    manager = ConnectionManager()
    user_id = uuid4()
    mock_ws = AsyncMock()

    await manager.connect(user_id, mock_ws)
    assert str(user_id) in manager.active_connections
    assert len(manager.active_connections[str(user_id)]) == 1
    mock_ws.accept.assert_awaited_once()

    manager.disconnect(user_id, mock_ws)
    assert str(user_id) not in manager.active_connections


@pytest.mark.asyncio
async def test_websocket_broadcast_analysis_payload_format():
    manager = ConnectionManager()
    user_id = uuid4()
    run_id = uuid4()
    video_id = uuid4()
    mock_ws = AsyncMock()

    await manager.connect(user_id, mock_ws)

    restaurant_data = {
        "id": 8,
        "name": "GIEF HO",
        "address": "34 Ngọc Khánh, Ba Đình, Hà Nội",
        "latitude": 21.0285,
        "longitude": 105.8154,
    }

    await manager.broadcast_analysis_update(
        user_id=user_id,
        analysis_run_id=run_id,
        video_id=video_id,
        status="COMPLETED",
        restaurant=restaurant_data,
        error_message=None,
    )

    mock_ws.send_text.assert_awaited_once()
    sent_text = mock_ws.send_text.call_args[0][0]
    payload = json.loads(sent_text)

    # Khớp chính xác đặc tả mục 5 README.md
    assert payload["event"] == "ANALYSIS_UPDATED"
    assert payload["data"]["analysis_run_id"] == str(run_id)
    assert payload["data"]["video_id"] == str(video_id)
    assert payload["data"]["status"] == "COMPLETED"
    assert payload["data"]["restaurant"]["name"] == "GIEF HO"
    assert payload["data"]["error_message"] is None
