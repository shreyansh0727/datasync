from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Any
import json
import logging
import tempfile
import os

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

# Store file chunks being assembled for Telegram
file_assembly = {}

@app.get("/")
async def root() -> Any:
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.websocket("/ws/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: str):
    await websocket.accept()
    room_manager.add_websocket(room_id, websocket)
    
    try:
        while True:
            message = await websocket.receive()
            
            if message.get("type") == "websocket.disconnect":
                break
            
            if "text" in message:
                data = message["text"]
                # Broadcast to other websockets
                await room_manager.broadcast_to_websockets(room_id, data)
                
                try:
                    msg_data = json.loads(data)
                    
                    # Handle text messages
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
                    
                    # Handle file metadata - prepare for assembly
                    elif msg_data.get('type') == 'file-meta':
                        file_id = msg_data.get('fileId')
                        file_assembly[file_id] = {
                            'name': msg_data.get('name'),
                            'size': msg_data.get('size'),
                            'mime': msg_data.get('mime'),
                            'total_chunks': msg_data.get('totalChunks'),
                            'chunks': [],
                            'sender': msg_data.get('sender', 'Web User'),
                            'room_id': room_id
                        }
                        logger.info(f"📥 Preparing to receive file: {msg_data.get('name')} ({file_id})")
                        
                        # Notify Telegram users
                        from bot.webhook import application
                        if application:
                            for chat_id in room_manager.get_telegram_users(room_id):
                                try:
                                    await application.bot.send_message(
                                        chat_id,
                                        f"📥 Receiving file from {msg_data.get('sender')}: {msg_data.get('name')} "
                                        f"({msg_data.get('size', 0)/1024/1024:.2f} MB)"
                                    )
                                except Exception:
                                    pass
                    
                    # Handle file chunk headers
                    elif msg_data.get('type') == 'file-header':
                        file_id = msg_data.get('fileId')
                        if file_id in file_assembly:
                            file_assembly[file_id]['pending_chunk'] = msg_data
                            
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
            elif "bytes" in message:
                binary_data = message["bytes"]
                # Broadcast to other websockets
                await room_manager.broadcast_binary_to_websockets(room_id, binary_data)
                
                # Collect chunks for Telegram upload
                for file_id, file_info in list(file_assembly.items()):
                    if file_info.get('pending_chunk') and file_info.get('room_id') == room_id:
                        chunk_info = file_info['pending_chunk']
                        file_info['chunks'].append({
                            'idx': chunk_info['idx'],
                            'data': binary_data
                        })
                        file_info.pop('pending_chunk', None)
                        
                        # Check if file is complete
                        if len(file_info['chunks']) == file_info['total_chunks']:
                            await send_file_to_telegram(file_id, file_info)
                            del file_assembly[file_id]
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from room {room_id}")
    except RuntimeError as e:
        if "disconnect" in str(e).lower():
            logger.info(f"WebSocket disconnect detected: {e}")
        else:
            logger.error(f"WebSocket runtime error: {e}")
    except Exception as e:
        logger.error(f"WebSocket error in room {room_id}: {e}")
    finally:
        room_manager.remove_websocket(room_id, websocket)


async def send_file_to_telegram(file_id: str, file_info: dict):
    """Assemble chunks and send file to Telegram users"""
    try:
        from bot.webhook import application
        if not application:
            logger.error("Bot application not initialized")
            return
        
        # Sort chunks by index
        file_info['chunks'].sort(key=lambda x: x['idx'])
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_info['name']}")
        temp_path = temp_file.name
        
        # Write all chunks to temp file
        with open(temp_path, 'wb') as f:
            for chunk in file_info['chunks']:
                f.write(chunk['data'])
        
        logger.info(f"📦 Assembled file: {file_info['name']} ({os.path.getsize(temp_path)} bytes)")
        
        # Send to all Telegram users in the room
        room_id = file_info['room_id']
        sender = file_info['sender']
        success_count = 0
        
        for chat_id in room_manager.get_telegram_users(room_id):
            try:
                with open(temp_path, 'rb') as f:
                    await application.bot.send_document(
                        chat_id,
                        document=f,
                        filename=file_info['name'],
                        caption=f"📎 From {sender} (Web)\n"
                                f"📁 {file_info['name']}\n"
                                f"💾 {file_info['size']/1024/1024:.2f} MB"
                    )
                success_count += 1
                logger.info(f"✅ Sent file to Telegram user {chat_id}")
            except Exception as e:
                logger.error(f"❌ Failed to send file to {chat_id}: {e}")
        
        # Clean up temp file
        os.unlink(temp_path)
        logger.info(f"✅ File sent to {success_count} Telegram user(s)")
        
    except Exception as e:
        logger.error(f"❌ Error sending file to Telegram: {e}")


@app.websocket("/signal/{room_id}")
async def websocket_signal(websocket: WebSocket, room_id: str):
    _signals: dict[str, set[WebSocket]] = {}
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
    except RuntimeError as e:
        if "disconnect" not in str(e).lower():
            logger.error(f"Signal WebSocket runtime error: {e}")
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
