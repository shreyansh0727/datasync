from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Any
import json

from .ws import RoomManager
from bot.webhook import bot_app, init_bot, shutdown_bot  # Import init functions

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="DataShare")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

# Mount Telegram bot webhook
app.mount("/bot", bot_app)

manager = RoomManager()

@app.get("/")
async def root() -> Any:
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    await manager.join(room_id, websocket)
    try:
        while True:
            # Receive either text (JSON) or binary (file chunks) messages
            message = await websocket.receive()
            
            if "text" in message:
                # Text message (metadata, chat messages)
                data = message["text"]
                await manager.broadcast_text(room_id, data)
            elif "bytes" in message:
                # Binary message (file chunk)
                binary_data = message["bytes"]
                await manager.broadcast_binary(room_id, binary_data)
    except WebSocketDisconnect:
        pass
    finally:
        manager.leave(room_id, websocket)

# Optional signaling endpoint
_signals: dict[str, set[WebSocket]] = {}

@app.websocket("/signal/{room_id}")
async def websocket_signal(websocket: WebSocket, room_id: str):
    await websocket.accept()
    _signals.setdefault(room_id, set()).add(websocket)
    try:
        while True:
            payload = await websocket.receive_text()
            for peer in list(_signals.get(room_id, set())):
                if peer is websocket:
                    continue
                try:
                    await peer.send_text(payload)
                except Exception:
                    _signals.get(room_id, set()).discard(peer)
    except WebSocketDisconnect:
        pass
    finally:
        _signals.get(room_id, set()).discard(websocket)
        if not _signals.get(room_id):
            _signals.pop(room_id, None)

# Bot initialization in main app startup
@app.on_event("startup")
async def startup_event():
    """Initialize Telegram bot on main app startup"""
    await init_bot()

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown Telegram bot on main app shutdown"""
    await shutdown_bot()
