from typing import Dict, Set, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class UnifiedRoomManager:
    """Manages rooms shared between web and telegram"""
    
    def __init__(self):
        self.rooms: Dict[str, Dict] = {}
        # Each room has:
        # {
        #   'websockets': set of WebSocket connections,
        #   'telegram_users': set of telegram chat_ids,
        #   'files': list of file metadata
        # }
    
    def create_room(self, room_id: str):
        """Create a new room"""
        if room_id not in self.rooms:
            self.rooms[room_id] = {
                'websockets': set(),
                'telegram_users': set(),
                'files': []
            }
            logger.info(f"📦 Created room: {room_id}")
    
    def add_websocket(self, room_id: str, websocket):
        """Add websocket to room"""
        self.create_room(room_id)
        self.rooms[room_id]['websockets'].add(websocket)
        logger.info(f"🌐 WebSocket joined room {room_id}")
    
    def remove_websocket(self, room_id: str, websocket):
        """Remove websocket from room"""
        if room_id in self.rooms:
            self.rooms[room_id]['websockets'].discard(websocket)
            self._cleanup_room(room_id)
    
    def add_telegram_user(self, room_id: str, chat_id: int):
        """Add telegram user to room"""
        self.create_room(room_id)
        self.rooms[room_id]['telegram_users'].add(chat_id)
        logger.info(f"📱 Telegram user {chat_id} joined room {room_id}")
    
    def remove_telegram_user(self, room_id: str, chat_id: int):
        """Remove telegram user from room"""
        if room_id in self.rooms:
            self.rooms[room_id]['telegram_users'].discard(chat_id)
            self._cleanup_room(room_id)
    
    def get_user_room(self, chat_id: int) -> Optional[str]:
        """Get room ID for telegram user"""
        for room_id, data in self.rooms.items():
            if chat_id in data['telegram_users']:
                return room_id
        return None
    
    def get_room_info(self, room_id: str) -> Dict:
        """Get room information"""
        if room_id not in self.rooms:
            return {'exists': False}
        
        room = self.rooms[room_id]
        return {
            'exists': True,
            'websocket_count': len(room['websockets']),
            'telegram_count': len(room['telegram_users']),
            'total_members': len(room['websockets']) + len(room['telegram_users']),
            'file_count': len(room['files'])
        }
    
    async def broadcast_to_websockets(self, room_id: str, data: str):
        """Broadcast text message to all websockets in room"""
        if room_id not in self.rooms:
            return
        
        for ws in list(self.rooms[room_id]['websockets']):
            try:
                await ws.send_text(data)
            except Exception as e:
                logger.error(f"Failed to send to websocket: {e}")
                self.rooms[room_id]['websockets'].discard(ws)
    
    async def broadcast_binary_to_websockets(self, room_id: str, data: bytes):
        """Broadcast binary data to all websockets in room"""
        if room_id not in self.rooms:
            return
        
        for ws in list(self.rooms[room_id]['websockets']):
            try:
                await ws.send_bytes(data)
            except Exception as e:
                logger.error(f"Failed to send binary to websocket: {e}")
                self.rooms[room_id]['websockets'].discard(ws)
    
    def get_telegram_users(self, room_id: str) -> Set[int]:
        """Get all telegram users in a room"""
        if room_id not in self.rooms:
            return set()
        return self.rooms[room_id]['telegram_users'].copy()
    
    def _cleanup_room(self, room_id: str):
        """Remove room if empty"""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            if not room['websockets'] and not room['telegram_users']:
                del self.rooms[room_id]
                logger.info(f"🗑️ Cleaned up empty room: {room_id}")

# Global instance
room_manager = UnifiedRoomManager()
