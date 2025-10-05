from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Any
import json
import logging

from bot.webhook import bot_app, init_bot, shutdown_bot
from shared.rooms import room_manager

logger = logging.getLogger(__name__)

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

app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
app.mount("/bot", bot_app)

@app.get("/")
async def root() -> Any:
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    room_manager.add_websocket(room_id, websocket)
    
    try:
        while True:
            try:
                message = await websocket.receive()
            except RuntimeError:
                # Connection already closed
                break
            
            if "text" in message:
                data = message["text"]
                # Broadcast to other websockets
                await room_manager.broadcast_to_websockets(room_id, data)
                
                # Also send to Telegram users in the room
                try:
                    msg_data = json.loads(data)
                    if msg_data.get('type') == 'msg':
                        from bot.webhook import application
                        if application:
                            for chat_id in room_manager.get_telegram_users(room_id):
                                try:
                                    await application.bot.send_message(
                                        chat_id,
                                        f"💬 {msg_data.get('sender', 'Web')}: {msg_data.get('text', '')}"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to send to telegram {chat_id}: {e}")
                    elif msg_data.get('type') == 'file-meta':
                        # Notify telegram users about incoming file
                        from bot.webhook import application
                        if application:
                            for chat_id in room_manager.get_telegram_users(room_id):
                                try:
                                    await application.bot.send_message(
                                        chat_id,
                                        f"📥 Receiving file: {msg_data.get('name')} ({msg_data.get('size', 0)/1024/1024:.2f} MB)"
                                    )
                                except Exception as e:
                                    logger.error(f"Failed to notify telegram: {e}")
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
            elif "bytes" in message:
                binary_data = message["bytes"]
                await room_manager.broadcast_binary_to_websockets(room_id, binary_data)
            
            elif message.get("type") == "websocket.disconnect":
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error in room {room_id}: {e}")
    finally:
        room_manager.remove_websocket(room_id, websocket)

@app.websocket("/signal/{room_id}")
async def websocket_signal(websocket: WebSocket, room_id: str):
    _signals: dict[str, set[WebSocket]] = {}
    await websocket.accept()
    _signals.setdefault(room_id, set()).add(websocket)
    
    try:
        while True:
            try:
                payload = await websocket.receive_text()
            except RuntimeError:
                break
                
            for peer in list(_signals.get(room_id, set())):
                if peer is websocket:
                    continue
                try:
                    await peer.send_text(payload)
                except Exception:
                    _signals.get(room_id, set()).discard(peer)
                    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Signal WebSocket error: {e}")
    finally:
        _signals.get(room_id, set()).discard(websocket)
        if not _signals.get(room_id):
            _signals.pop(room_id, None)

@app.on_event("startup")
async def startup_event():
    await init_bot()

@app.on_event("shutdown")
async def shutdown_event():
    await shutdown_bot()
