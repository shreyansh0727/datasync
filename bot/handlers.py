import logging
from typing import Dict, Set
from telegram import Update
from telegram.ext import ContextTypes
import random
import json

logger = logging.getLogger(__name__)

# Import unified room manager
from shared.rooms import room_manager

def generate_room_id() -> str:
    """Generate a 6-character room ID"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(6))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome_text = (
        "🚀 Welcome to DataShare Bot!\n\n"
        "Share files instantly across devices using room codes.\n\n"
        "Commands:\n"
        "/create - Create a new room\n"
        "/join ROOM_ID - Join an existing room\n"
        "/leave - Leave current room\n"
        "/room - Show current room info\n"
        "/help - Show this help message\n\n"
        "💡 How it works:\n"
        "1. Create or join a room\n"
        "2. Share the room ID with others\n"
        "3. Send files/messages - everyone receives them!\n"
        "4. Works with web interface too!"
    )
    await update.message.reply_text(welcome_text)


async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new room"""
    chat_id = update.effective_chat.id
    room_id = generate_room_id()
    
    # Add to unified room manager
    room_manager.add_telegram_user(room_id, chat_id)
    
    await update.message.reply_text(
        f"✅ Room Created!\n\n"
        f"🔑 Room ID: {room_id}\n"
        f"👥 Members: 1\n\n"
        f"Share this code:\n/join {room_id}\n\n"
        f"Or open on web:\nhttps://datasync-rgfv.onrender.com/?room={room_id}"
    )


async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an existing room"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /join ROOM_ID")
        return
    
    room_id = context.args[0].upper()
    
    # Leave old room
    old_room = room_manager.get_user_room(chat_id)
    if old_room:
        room_manager.remove_telegram_user(old_room, chat_id)
    
    # Join new room
    room_manager.add_telegram_user(room_id, chat_id)
    
    # Get room info
    info = room_manager.get_room_info(room_id)
    
    # Notify websocket users
    notification = json.dumps({
        'type': 'msg',
        'sender': 'System',
        'text': f'📱 Telegram user joined room {room_id}'
    })
    await room_manager.broadcast_to_websockets(room_id, notification)
    
    await update.message.reply_text(
        f"✅ Joined Room!\n\n"
        f"🔑 Room: {room_id}\n"
        f"👥 Total Members: {info['total_members']}\n"
        f"  - Web: {info['websocket_count']}\n"
        f"  - Telegram: {info['telegram_count']}\n\n"
        f"Send files/messages now!"
    )


async def leave_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave current room"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ You're not in any room.")
        return
    
    room_manager.remove_telegram_user(room_id, chat_id)
    await update.message.reply_text(f"✅ Left room {room_id}")


async def room_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current room info"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ Not in any room.\nUse /create or /join")
        return
    
    info = room_manager.get_room_info(room_id)
    
    await update.message.reply_text(
        f"📊 Room Info\n\n"
        f"🔑 ID: {room_id}\n"
        f"👥 Total Members: {info['total_members']}\n"
        f"  - 🌐 Web users: {info['websocket_count']}\n"
        f"  - 📱 Telegram users: {info['telegram_count']}\n"
        f"📁 Files shared: {info['file_count']}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast text messages"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    text = update.message.text
    sender = update.effective_user.first_name
    
    # Send to other telegram users
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_message(member_id, f"💬 {sender}: {text}")
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    # Send to web users
    web_msg = json.dumps({
        'type': 'msg',
        'sender': f'{sender} (Telegram)',
        'text': text
    })
    await room_manager.broadcast_to_websockets(room_id, web_msg)
    
    await update.message.reply_text("✅ Sent")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast documents"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    doc = update.message.document
    sender = update.effective_user.first_name
    
    msg = await update.message.reply_text("📤 Sharing...")
    success = 0
    
    # Send to other telegram users
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_document(
                    member_id,
                    doc.file_id,
                    caption=f"📎 From {sender}\n📁 {doc.file_name}\n💾 {doc.file_size/1024/1024:.2f} MB"
                )
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    # Notify web users (they can't receive the actual file via websocket easily)
    web_notification = json.dumps({
        'type': 'msg',
        'sender': 'System',
        'text': f'📎 {sender} shared a file via Telegram: {doc.file_name} ({doc.file_size/1024/1024:.2f} MB)'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await msg.edit_text(f"✅ Shared with {success} Telegram user(s) + web users notified")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast photos"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    photo = update.message.photo[-1]
    sender = update.effective_user.first_name
    
    success = 0
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_photo(member_id, photo.file_id, caption=f"📷 From {sender}")
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    # Notify web
    web_notification = json.dumps({
        'type': 'msg',
        'sender': 'System',
        'text': f'📷 {sender} shared a photo via Telegram'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await update.message.reply_text(f"✅ Shared with {success} Telegram user(s) + web users notified")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast videos"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    video = update.message.video
    sender = update.effective_user.first_name
    
    msg = await update.message.reply_text("📤 Sharing video...")
    success = 0
    
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_video(member_id, video.file_id, caption=f"🎥 From {sender}")
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    # Notify web
    web_notification = json.dumps({
        'type': 'msg',
        'sender': 'System',
        'text': f'🎥 {sender} shared a video via Telegram'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await msg.edit_text(f"✅ Shared with {success} Telegram user(s) + web users notified")
