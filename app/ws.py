from typing import Dict, Set
from fastapi import WebSocket

class RoomManager:
    def __init__(self) -> None:
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def join(self, room_id: str, websocket: WebSocket) -> None:
        self.rooms.setdefault(room_id, set()).add(websocket)

    def leave(self, room_id: str, websocket: WebSocket) -> None:
        if room_id in self.rooms:
            self.rooms[room_id].discard(websocket)
            if not self.rooms[room_id]:
                self.rooms.pop(room_id, None)

    async def broadcast_text(self, room_id: str, message: str) -> None:
        """Broadcast text (JSON) messages"""
        for ws in list(self.rooms.get(room_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                self.rooms.get(room_id, set()).discard(ws)

    async def broadcast_binary(self, room_id: str, data: bytes) -> None:
        """Broadcast binary data (file chunks)"""
        for ws in list(self.rooms.get(room_id, set())):
            try:
                await ws.send_bytes(data)
            except Exception:
                self.rooms.get(room_id, set()).discard(ws)
