import os
import logging
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
from bot.handlers import (
    start, create_room, join_room, leave_room, room_info,
    handle_message, handle_document, handle_photo, handle_video
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Create Telegram application
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
application = Application.builder().token(TOKEN).build()

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", start))
application.add_handler(CommandHandler("create", create_room))
application.add_handler(CommandHandler("join", join_room))
application.add_handler(CommandHandler("leave", leave_room))
application.add_handler(CommandHandler("room", room_info))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
application.add_handler(MessageHandler(filters.VIDEO, handle_video))

# FastAPI app for webhook
bot_app = FastAPI()

@bot_app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(status_code=500)

@bot_app.get("/")
async def bot_health():
    """Health check for bot"""
    return {"status": "Bot is running", "bot": "DataShare Telegram Bot"}

@bot_app.on_event("startup")
async def on_startup():
    """Set webhook on startup"""
    await application.initialize()
    webhook_url = os.getenv("WEBHOOK_URL")
    if webhook_url:
        full_url = f"{webhook_url}/bot/webhook"
        await application.bot.set_webhook(url=full_url)
        logger.info(f"Webhook set to: {full_url}")
    else:
        logger.warning("WEBHOOK_URL not set - bot will not receive updates")

@bot_app.on_event("shutdown")
async def on_shutdown():
    """Clean up on shutdown"""
    await application.shutdown()
