import logging
from typing import Dict, Set
from telegram import Update
from telegram.ext import ContextTypes
import random
import json
import asyncio

logger = logging.getLogger(__name__)

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
        "4. Works with web interface too!\n\n"
        "📱 Files sent via Telegram → delivered to web users\n"
        "🌐 Files sent via web → delivered to Telegram users"
    )
    await update.message.reply_text(welcome_text)


async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new room"""
    chat_id = update.effective_chat.id
    room_id = generate_room_id()
    
    room_manager.add_telegram_user(room_id, chat_id)
    
    await update.message.reply_text(
        f"✅ Room Created!\n\n"
        f"🔑 Room ID: {room_id}\n"
        f"👥 Members: 1\n\n"
        f"📱 Share with Telegram users:\n/join {room_id}\n\n"
        f"🌐 Share with web users:\nhttps://datasync-rgfv.onrender.com/?room={room_id}"
    )


async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an existing room"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /join ROOM_ID")
        return
    
    room_id = context.args[0].upper()
    
    old_room = room_manager.get_user_room(chat_id)
    if old_room:
        room_manager.remove_telegram_user(old_room, chat_id)
    
    room_manager.add_telegram_user(room_id, chat_id)
    info = room_manager.get_room_info(room_id)
    
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
        f"  - 🌐 Web: {info['websocket_count']}\n"
        f"  - 📱 Telegram: {info['telegram_count']}\n\n"
        f"Send files/messages - they'll be delivered to everyone!"
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
    
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_message(member_id, f"💬 {sender}: {text}")
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    web_msg = json.dumps({
        'type': 'msg',
        'sender': f'{sender} (Telegram)',
        'text': text
    })
    await room_manager.broadcast_to_websockets(room_id, web_msg)
    
    await update.message.reply_text("✅ Sent to all members")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast documents - now with full web transfer"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text("⚠️ Join a room first!")
        return
    
    doc = update.message.document
    sender = update.effective_user.first_name
    
    msg = await update.message.reply_text("📤 Sharing file to all users...")
    telegram_success = 0
    
    # Send to other telegram users
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_document(
                    member_id,
                    doc.file_id,
                    caption=f"📎 From {sender}\n📁 {doc.file_name}\n💾 {doc.file_size/1024/1024:.2f} MB"
                )
                telegram_success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    # Send to web users - download and transfer
    info = room_manager.get_room_info(room_id)
    if info['websocket_count'] > 0:
        try:
            await msg.edit_text("📤 Downloading file for web users...")
            
            # Download file from Telegram
            file = await context.bot.get_file(doc.file_id)
            file_bytes = await file.download_as_bytearray()
            
            await msg.edit_text("📤 Sending file to web users...")
            
            # Send file metadata to web
            file_id = f"tg_{doc.file_unique_id}"
            chunk_size = 256 * 1024
            total_chunks = (len(file_bytes) + chunk_size - 1) // chunk_size
            
            metadata = json.dumps({
                'type': 'file-meta',
                'name': doc.file_name,
                'size': len(file_bytes),
                'mime': doc.mime_type or 'application/octet-stream',
                'totalChunks': total_chunks,
                'fileId': file_id,
                'sender': f'{sender} (Telegram)'
            })
            await room_manager.broadcast_to_websockets(room_id, metadata)
            
            # Send file in chunks
            for i in range(total_chunks):
                start = i * chunk_size
                end = min((i + 1) * chunk_size, len(file_bytes))
                chunk = bytes(file_bytes[start:end])
                
                # Send chunk header
                header = json.dumps({
                    'type': 'file-header',
                    'fileId': file_id,
                    'idx': i,
                    'total': total_chunks,
                    'size': len(chunk)
                })
                await room_manager.broadcast_to_websockets(room_id, header)
                
                # Send binary chunk
                await room_manager.broadcast_binary_to_websockets(room_id, chunk)
                
                # Small delay to prevent overwhelming
                if i % 10 == 0:
                    await asyncio.sleep(0.01)
            
            await msg.edit_text(
                f"✅ File shared!\n"
                f"📱 Sent to {telegram_success} Telegram user(s)\n"
                f"🌐 Sent to {info['websocket_count']} web user(s)"
            )
            
        except Exception as e:
            logger.error(f"Error sending file to web: {e}")
            await msg.edit_text(
                f"✅ Sent to {telegram_success} Telegram user(s)\n"
                f"❌ Failed to send to web users: {str(e)}"
            )
    else:
        await msg.edit_text(f"✅ Sent to {telegram_success} Telegram user(s)")


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
    
    # Notify web users
    web_notification = json.dumps({
        'type': 'msg',
        'sender': 'System',
        'text': f'📷 {sender} shared a photo (Telegram only - use documents for cross-platform)'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await update.message.reply_text(f"✅ Shared with {success} Telegram user(s)\n💡 Tip: Send as document for web users to receive")


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
    
    web_notification = json.dumps({
        'type': 'msg',
        'sender': 'System',
        'text': f'🎥 {sender} shared a video (Telegram only - use documents for cross-platform)'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await msg.edit_text(f"✅ Shared with {success} Telegram user(s)\n💡 Tip: Send as document for web users to receive")
