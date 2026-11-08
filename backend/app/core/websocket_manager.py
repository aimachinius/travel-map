import json
import logging
from typing import Any
from uuid import UUID

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # Map user_id (string or UUID) -> list of active WebSockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str | UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        uid = str(user_id)
        if uid not in self.active_connections:
            self.active_connections[uid] = []
        self.active_connections[uid].append(websocket)
        logger.info(f"WebSocket connected for user {uid}. Total clients: {len(self.active_connections[uid])}")

    def disconnect(self, user_id: str | UUID, websocket: WebSocket) -> None:
        uid = str(user_id)
        if uid in self.active_connections:
            if websocket in self.active_connections[uid]:
                self.active_connections[uid].remove(websocket)
            if not self.active_connections[uid]:
                del self.active_connections[uid]
        logger.info(f"WebSocket disconnected for user {uid}")

    async def send_personal_message(self, message: dict[str, Any], websocket: WebSocket) -> None:
        await websocket.send_text(json.dumps(message, default=str))

    async def send_to_user(self, user_id: str | UUID, message: dict[str, Any]) -> None:
        uid = str(user_id)
        if uid not in self.active_connections:
            return

        dead_connections: list[WebSocket] = []
        payload = json.dumps(message, default=str)

        for connection in list(self.active_connections[uid]):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send WS message to user {uid}: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(user_id, dead)

    async def broadcast_analysis_update(
        self,
        user_id: str | UUID,
        analysis_run_id: str | UUID | int,
        video_id: str | UUID | int | None,
        status: str,
        restaurant: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        message = {
            "event": "ANALYSIS_UPDATED",
            "data": {
                "analysis_run_id": str(analysis_run_id) if isinstance(analysis_run_id, UUID) else analysis_run_id,
                "video_id": str(video_id) if isinstance(video_id, UUID) else video_id,
                "status": status,
                "restaurant": restaurant,
                "error_message": error_message,
            },
        }
        await self.send_to_user(user_id, message)


websocket_manager = ConnectionManager()
