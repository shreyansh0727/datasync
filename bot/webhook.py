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

# Get token but don't build application yet
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Global variable to hold application (initialized in startup)
application = None

# FastAPI app for webhook
bot_app = FastAPI()

@bot_app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    if not application:
        return Response(content="Bot not initialized", status_code=503)
    
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
    status = "running" if application else "initializing"
    return {"status": f"Bot is {status}", "bot": "DataShare Telegram Bot"}

@bot_app.on_event("startup")
async def on_startup():
    """Initialize bot and set webhook on startup"""
    global application
    
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment!")
        return
    
    try:
        # Build application during startup, not at import time
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
        
        # Initialize the application
        await application.initialize()
        
        # Set webhook
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            full_url = f"{webhook_url}/bot/webhook"
            await application.bot.set_webhook(url=full_url)
            logger.info(f"✅ Webhook set to: {full_url}")
        else:
            logger.warning("⚠️ WEBHOOK_URL not set - bot will not receive updates")
            logger.info("Add WEBHOOK_URL environment variable in Render dashboard")
        
        logger.info("✅ Telegram bot initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot: {e}")

@bot_app.on_event("shutdown")
async def on_shutdown():
    """Clean up on shutdown"""
    if application:
        try:
            await application.shutdown()
            logger.info("Bot shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
