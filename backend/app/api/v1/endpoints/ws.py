import logging
from uuid import UUID

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import settings
from app.core.websocket_manager import websocket_manager
from app.db.session import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """
    WebSocket endpoint nhận thông báo thời gian thực về tiến trình phân tích video.
    URL: WS /api/v1/ws?token=<JWT_ACCESS_TOKEN>
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Xác thực token
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id_str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_uuid = UUID(user_id_str)
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Kiểm tra user trong DB
    db = SessionLocal()
    try:
        user = db.get(User, user_uuid)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    # Chấp nhận kết nối
    await websocket_manager.connect(user_uuid, websocket)

    try:
        while True:
            # Lắng nghe keep-alive / ping từ client
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        websocket_manager.disconnect(user_uuid, websocket)
    except Exception as exc:
        logger.warning(f"WebSocket connection error for user {user_uuid}: {exc}")
        websocket_manager.disconnect(user_uuid, websocket)
