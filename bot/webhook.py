import os
import logging
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,  # Add this import
    filters,
)
from bot.handlers import (
    start, create_room, join_room, leave_room, room_info,
    handle_message, handle_document, handle_photo, handle_video,
    button_callback  # Add this import
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
application = None

bot_app = FastAPI()

@bot_app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    if not application:
        logger.error("❌ Bot not initialized")
        return Response(content="Bot not initialized", status_code=503)
    
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return Response(status_code=500)

@bot_app.get("/")
async def bot_health():
    """Health check"""
    status = "running" if application else "not initialized"
    has_token = "yes" if TOKEN else "no"
    return {
        "status": f"Bot is {status}",
        "bot": "DataShare Telegram Bot",
        "token_set": has_token
    }

async def init_bot():
    """Initialize bot for webhook-only mode"""
    global application
    
    logger.info("🚀 Starting bot initialization...")
    
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return
    
    logger.info(f"✅ Token found: {TOKEN[:10]}...{TOKEN[-5:]}")
    
    try:
        logger.info("📦 Building Telegram application (webhook mode)...")
        application = (
            Application.builder()
            .token(TOKEN)
            .updater(None)
            .build()
        )
        logger.info("✅ Application built")
        
        # Add handlers
        logger.info("🔧 Adding handlers...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", start))
        application.add_handler(CommandHandler("create", create_room))
        application.add_handler(CommandHandler("join", join_room))
        application.add_handler(CommandHandler("leave", leave_room))
        application.add_handler(CommandHandler("room", room_info))
        
        # Add callback query handler for buttons
        application.add_handler(CallbackQueryHandler(button_callback))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.VIDEO, handle_video))
        logger.info("✅ Handlers added")
        
        # Initialize
        logger.info("🔄 Initializing application...")
        await application.initialize()
        await application.start()
        logger.info("✅ Application initialized and started")
        
        # Set webhook
        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            webhook_url = "https://datasync-rgfv.onrender.com"
            logger.warning(f"⚠️ WEBHOOK_URL not set, using default: {webhook_url}")
        
        full_url = f"{webhook_url}/bot/webhook"
        logger.info(f"🌐 Setting webhook to: {full_url}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await application.bot.set_webhook(url=full_url)
                if result:
                    logger.info(f"✅✅✅ Webhook set successfully! ✅✅✅")
                    import asyncio
                    await asyncio.sleep(1)
                    webhook_info = await application.bot.get_webhook_info()
                    logger.info(f"📍 Current webhook: {webhook_info.url}")
                    if webhook_info.url == full_url:
                        logger.info("✅ Webhook verified!")
                    else:
                        logger.warning(f"⚠️ Webhook mismatch! Expected {full_url}, got {webhook_info.url}")
                    break
            except Exception as e:
                logger.error(f"❌ Webhook attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info("⏳ Retrying in 2 seconds...")
                    import asyncio
                    await asyncio.sleep(2)
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot: {e}")
        logger.exception("Full traceback:")

async def shutdown_bot():
    """Shutdown bot"""
    if application:
        try:
            logger.info("🛑 Shutting down bot...")
            await application.stop()
            await application.shutdown()
            logger.info("✅ Bot shutdown complete")
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
