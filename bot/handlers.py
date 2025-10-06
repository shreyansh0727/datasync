import logging
from typing import Dict, Set
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    """Send welcome message with inline keyboard"""
    welcome_text = (
        "✨ <b>Welcome to DataSync!</b> ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 Share files <b>instantly</b> across devices\n"
        "🌐 Works on <b>Web & Telegram</b>\n"
        "🔒 Room-based secure sharing\n"
        "⚡️ Real-time synchronization\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <b>Quick Start Guide:</b>\n\n"
        "1️⃣ Create or join a room\n"
        "2️⃣ Share the room code\n"
        "3️⃣ Start sharing files & messages\n"
        "4️⃣ Everyone receives instantly!\n\n"
        "🎯 <b>Cross-Platform Magic:</b>\n"
        "• 📱 Telegram → 🌐 Web ✅\n"
        "• 🌐 Web → 📱 Telegram ✅\n"
        "• 📱 Telegram → 📱 Telegram ✅\n\n"
        "Ready to get started? 🎉"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎨 Create New Room", callback_data="create_room")],
        [InlineKeyboardButton("🚪 Join Existing Room", callback_data="join_prompt")],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def create_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Create a new room with fancy formatting"""
    chat_id = update.effective_chat.id
    room_id = generate_room_id()
    
    room_manager.add_telegram_user(room_id, chat_id)
    
    message_text = (
        "🎉 <b>Room Created Successfully!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 <b>Room ID:</b> <code>{room_id}</code>\n"
        f"👥 <b>Members:</b> 1 (You)\n"
        f"🌟 <b>Status:</b> Active & Ready\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📱 <b>Share with Telegram users:</b>\n"
        f"👉 /join {room_id}\n\n"
        "🌐 <b>Share with web users:</b>\n"
        f"👉 https://datasync-rgfv.onrender.com/?room={room_id}\n\n"
        "💬 Send any file or message now!\n"
        "Everyone in the room will receive it instantly! ⚡️"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Room Info", callback_data="room_info")],
        [InlineKeyboardButton("🚪 Leave Room", callback_data="leave_room")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message_text,
        parse_mode='HTML',
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


async def join_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Join an existing room with modern design"""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text(
            "⚠️ <b>Oops! Missing Room ID</b>\n\n"
            "Please use this format:\n"
            "👉 <code>/join ABC123</code>\n\n"
            "💡 <b>Tip:</b> Get the room ID from the person who created it!",
            parse_mode='HTML'
        )
        return
    
    room_id = context.args[0].upper()
    
    old_room = room_manager.get_user_room(chat_id)
    if old_room:
        room_manager.remove_telegram_user(old_room, chat_id)
    
    room_manager.add_telegram_user(room_id, chat_id)
    info = room_manager.get_room_info(room_id)
    
    notification = json.dumps({
        'type': 'msg',
        'sender': '🎉 System',
        'text': f'New member joined room {room_id}! Welcome! 👋'
    })
    await room_manager.broadcast_to_websockets(room_id, notification)
    
    message_text = (
        "✅ <b>You're In!</b> Welcome to the room! 🎊\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 <b>Room:</b> <code>{room_id}</code>\n"
        f"👥 <b>Total Members:</b> {info['total_members']}\n"
        f"├─ 🌐 Web users: {info['websocket_count']}\n"
        f"└─ 📱 Telegram users: {info['telegram_count']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>You can now:</b>\n"
        "• 📎 Share any files\n"
        "• 💬 Send messages\n"
        "• 📷 Share photos as documents\n\n"
        "Everything syncs <b>instantly</b> across all devices! ⚡️"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Room Info", callback_data="room_info")],
        [InlineKeyboardButton("🚪 Leave Room", callback_data="leave_room")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def leave_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave current room"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text(
            "🤔 <b>Not in any room yet!</b>\n\n"
            "Use /create to make a new room\n"
            "or /join ROOM_ID to join one! 🚀",
            parse_mode='HTML'
        )
        return
    
    room_manager.remove_telegram_user(room_id, chat_id)
    
    await update.message.reply_text(
        f"👋 <b>Left room</b> <code>{room_id}</code>\n\n"
        "Thanks for using DataSync!\n"
        "Create or join another room anytime! 🎉\n\n"
        "Type /start to see options",
        parse_mode='HTML'
    )


async def room_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current room info with stats"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text(
            "🤔 <b>You're not in any room!</b>\n\n"
            "Ready to start? Try:\n"
            "• /create - Make a new room\n"
            "• /join ROOM_ID - Join existing",
            parse_mode='HTML'
        )
        return
    
    info = room_manager.get_room_info(room_id)
    
    message_text = (
        "📊 <b>Room Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔑 <b>Room ID:</b> <code>{room_id}</code>\n\n"
        f"👥 <b>Total Members:</b> {info['total_members']}\n"
        f"├─ 🌐 Web users: {info['websocket_count']}\n"
        f"└─ 📱 Telegram users: {info['telegram_count']}\n\n"
        f"📁 <b>Files Shared:</b> {info['file_count']}\n"
        f"🌟 <b>Status:</b> Active\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 Share the room ID to invite more people!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="room_info")],
        [InlineKeyboardButton("🚪 Leave Room", callback_data="leave_room")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast text messages"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text(
            "⚠️ <b>Join a room first!</b>\n\n"
            "Use /create or /join ROOM_ID",
            parse_mode='HTML'
        )
        return
    
    text = update.message.text
    sender = update.effective_user.first_name
    
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_message(
                    member_id, 
                    f"💬 <b>{sender}:</b> {text}", 
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    web_msg = json.dumps({
        'type': 'msg',
        'sender': f'{sender} (Telegram)',
        'text': text
    })
    await room_manager.broadcast_to_websockets(room_id, web_msg)
    
    await update.message.reply_text("✅ Delivered to everyone! ⚡️")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast documents with progress indicators"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text(
            "⚠️ <b>Join a room first!</b>\n\n"
            "Use /create or /join ROOM_ID",
            parse_mode='HTML'
        )
        return
    
    doc = update.message.document
    sender = update.effective_user.first_name
    
    msg = await update.message.reply_text(
        "📤 <b>Preparing to send file...</b>\n"
        "⏳ Please wait...",
        parse_mode='HTML'
    )
    telegram_success = 0
    
    # Send to other telegram users
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_document(
                    member_id,
                    doc.file_id,
                    caption=f"📎 <b>From {sender}</b>\n📁 {doc.file_name}\n💾 {doc.file_size/1024/1024:.2f} MB",
                    parse_mode='HTML'
                )
                telegram_success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    # Send to web users
    info = room_manager.get_room_info(room_id)
    if info['websocket_count'] > 0:
        try:
            await msg.edit_text(
                "⬇️ <b>Downloading from Telegram...</b>\n"
                "⏳ This may take a moment",
                parse_mode='HTML'
            )
            
            file = await context.bot.get_file(doc.file_id)
            file_bytes = await file.download_as_bytearray()
            
            await msg.edit_text(
                "📤 <b>Sending to web users...</b>\n"
                "⏳ Almost there!",
                parse_mode='HTML'
            )
            
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
            
            for i in range(total_chunks):
                start = i * chunk_size
                end = min((i + 1) * chunk_size, len(file_bytes))
                chunk = bytes(file_bytes[start:end])
                
                header = json.dumps({
                    'type': 'file-header',
                    'fileId': file_id,
                    'idx': i,
                    'total': total_chunks,
                    'size': len(chunk)
                })
                await room_manager.broadcast_to_websockets(room_id, header)
                await room_manager.broadcast_binary_to_websockets(room_id, chunk)
                
                if i % 10 == 0:
                    await asyncio.sleep(0.01)
            
            await msg.edit_text(
                "✅ <b>File Shared Successfully!</b> 🎉\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📱 Telegram users: {telegram_success}\n"
                f"🌐 Web users: {info['websocket_count']}\n\n"
                "Everyone has received your file! ⚡️",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error(f"Error sending file to web: {e}")
            await msg.edit_text(
                f"⚠️ <b>Partial Success</b>\n\n"
                f"✅ Sent to {telegram_success} Telegram users\n"
                f"❌ Web transfer failed\n\n"
                f"Error: {str(e)[:50]}...",
                parse_mode='HTML'
            )
    else:
        await msg.edit_text(
            "✅ <b>File Delivered!</b>\n\n"
            f"📱 Sent to {telegram_success} Telegram user(s)\n"
            f"🌐 No web users currently online",
            parse_mode='HTML'
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast photos"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text(
            "⚠️ <b>Join a room first!</b>\n\n"
            "Use /create or /join ROOM_ID",
            parse_mode='HTML'
        )
        return
    
    photo = update.message.photo[-1]
    sender = update.effective_user.first_name
    
    success = 0
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_photo(
                    member_id, 
                    photo.file_id, 
                    caption=f"📷 From <b>{sender}</b>", 
                    parse_mode='HTML'
                )
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    web_notification = json.dumps({
        'type': 'msg',
        'sender': '🖼️ System',
        'text': f'{sender} shared a photo (Telegram only)'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await update.message.reply_text(
        f"✅ Photo sent to {success} Telegram user(s)\n\n"
        f"💡 <b>Pro Tip:</b> Send photos as <b>documents</b>\n"
        f"to share with web users too! 🌐",
        parse_mode='HTML'
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast videos"""
    chat_id = update.effective_chat.id
    
    room_id = room_manager.get_user_room(chat_id)
    if not room_id:
        await update.message.reply_text(
            "⚠️ <b>Join a room first!</b>\n\n"
            "Use /create or /join ROOM_ID",
            parse_mode='HTML'
        )
        return
    
    video = update.message.video
    sender = update.effective_user.first_name
    
    msg = await update.message.reply_text(
        "📤 <b>Sending video...</b> ⏳", 
        parse_mode='HTML'
    )
    success = 0
    
    for member_id in room_manager.get_telegram_users(room_id):
        if member_id != chat_id:
            try:
                await context.bot.send_video(
                    member_id, 
                    video.file_id, 
                    caption=f"🎥 From <b>{sender}</b>", 
                    parse_mode='HTML'
                )
                success += 1
            except Exception as e:
                logger.error(f"Send failed: {e}")
    
    web_notification = json.dumps({
        'type': 'msg',
        'sender': '🎬 System',
        'text': f'{sender} shared a video (Telegram only)'
    })
    await room_manager.broadcast_to_websockets(room_id, web_notification)
    
    await msg.edit_text(
        f"✅ Video sent to {success} Telegram user(s)! 🎉\n\n"
        f"💡 <b>Pro Tip:</b> Send videos as <b>documents</b>\n"
        f"to enable cross-platform sharing! 🌐",
        parse_mode='HTML'
    )
