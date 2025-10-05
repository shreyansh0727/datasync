import logging
from typing import Dict, Set
from telegram import Update
from telegram.ext import ContextTypes
import random

logger = logging.getLogger(__name__)

# Store active rooms and their members
rooms: Dict[str, Set[int]] = {}
user_rooms: Dict[int, str] = {}
room_files: Dict[str, list] = {}


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
        "3. Send files/messages - everyone receives them!"
    )
    await update.message.reply_text(welcome_text)


async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new room"""
    chat_id = update.effective_chat.id
    room_id = generate_room_id()
    
    rooms[room_id] = {chat_id}
    user_rooms[chat_id] = room_id
    room_files[room_id] = []
    
    await update.message.reply_text(
        f"✅ Room Created!\n\n"
        f"🔑 Room ID: {room_id}\n"
        f"👥 Members: 1\n\n"
        f"Share this code:\n/join {room_id}"
    )


async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an existing room"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /join ROOM_ID")
        return
    
    room_id = context.args[0].upper()
    
    if room_id not in rooms:
        await update.message.reply_text(
            f"❌ Room {room_id} not found.\nCreate one with /create"
        )
        return
    
    # Leave old room if exists
    if chat_id in user_rooms:
        old_room = user_rooms[chat_id]
        rooms[old_room].discard(chat_id)
    
    # Join new room
    rooms[room_id].add(chat_id)
    user_rooms[chat_id] = room_id
    
    # Notify others
    for member_id in rooms[room_id]:
        if member_id != chat_id:
            try:
                await context.bot.send_message(
                    member_id,
                    f"👤 New member joined {room_id}"
                )
            except Exception:
                pass
    
    await update.message.reply_text(
        f"✅ Joined Room!\n\n"
        f"🔑 Room: {room_id}\n"
        f"👥 Members: {len(rooms[room_id])}\n\n"
        f"Send files/messages now!"
    )


async def leave_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave current room"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_rooms:
        await update.message.reply_text("⚠️ You're not in any room.")
        return
    
    room_id = user_rooms[chat_id]
    rooms[room_id].discard(chat_id)
    del user_rooms[chat_id]
    
    if not rooms[room_id]:
        del rooms[room_id]
        del room_files[room_id]
    
    await update.message.reply_text(f"✅ Left room {room_id}")


async def room_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current room info"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_rooms:
        await update.message.reply_text(
            "⚠️ Not in any room.\nUse /create or /join"
        )
        return
    
    room_id = user_rooms[chat_id]
    member_count = len(rooms[room_id])
    file_count = len(room_files.get(room_id, []))
    
    await update.message.reply_text(
        f"📊 Room Info\n\n"
        f"🔑 ID: {room_id}\n"
        f"👥 Members: {member_count}\n"
        f"📁 Files: {file_count}"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast text messages"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_rooms:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    room_id = user_rooms[chat_id]
    text = update.message.text
    sender = update.effective_user.first_name
    
    for member_id in rooms[room_id]:
        if member_id != chat_id:
            try:
                await context.bot.send_message(
                    member_id,
                    f"💬 {sender}: {text}"
                )
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    await update.message.reply_text("✅ Sent")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast documents"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_rooms:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    room_id = user_rooms[chat_id]
    doc = update.message.document
    sender = update.effective_user.first_name
    
    room_files[room_id].append({
        'file_id': doc.file_id,
        'name': doc.file_name,
        'size': doc.file_size
    })
    
    msg = await update.message.reply_text("📤 Sharing...")
    success = 0
    
    for member_id in rooms[room_id]:
        if member_id != chat_id:
            try:
                await context.bot.send_document(
                    member_id,
                    doc.file_id,
                    caption=f"📎 From {sender}\n"
                            f"📁 {doc.file_name}\n"
                            f"💾 {doc.file_size/1024/1024:.2f} MB"
                )
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    await msg.edit_text(f"✅ Shared with {success} member(s)")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast photos"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_rooms:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    room_id = user_rooms[chat_id]
    photo = update.message.photo[-1]
    sender = update.effective_user.first_name
    
    success = 0
    for member_id in rooms[room_id]:
        if member_id != chat_id:
            try:
                await context.bot.send_photo(
                    member_id,
                    photo.file_id,
                    caption=f"📷 From {sender}"
                )
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    await update.message.reply_text(f"✅ Shared with {success} member(s)")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast videos"""
    chat_id = update.effective_chat.id
    
    if chat_id not in user_rooms:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    room_id = user_rooms[chat_id]
    video = update.message.video
    sender = update.effective_user.first_name
    
    msg = await update.message.reply_text("📤 Sharing video...")
    success = 0
    
    for member_id in rooms[room_id]:
        if member_id != chat_id:
            try:
                await context.bot.send_video(
                    member_id,
                    video.file_id,
                    caption=f"🎥 From {sender}"
                )
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    await msg.edit_text(f"✅ Shared with {success} member(s)")
