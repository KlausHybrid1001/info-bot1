import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI, Request
import logging
import asyncio

# Constants
BOT_TOKEN = "7597041420:AAGxS7T7fnwenj1FvlpR1bEl5niRm_tCAzU"
APP_URL = "https://info-bot1-1.onrender.com"  # Replace with your Render app URL

# Initialize FastAPI and Telegram Bot application
app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    await update.message.reply_text("Welcome! Send the DL number directly to get the PDF.")

async def handle_dl_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for processing DL numbers"""
    dl_number = update.message.text.strip()
    if not dl_number:
        await update.message.reply_text("❌ Please provide a valid DL number.")
        return
    # Simulate PDF generation and send a placeholder response
    await update.message.reply_text(f"Processing DL number: {dl_number}.")
    await update.message.reply_text("✅ Here is a placeholder for your PDF file.")

# Add handlers to the Telegram bot
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dl_number))

# FastAPI route for handling webhooks
@app.post("/webhook/{token}")
async def webhook_handler(token: str, request: Request):
    """Webhook handler to process incoming updates"""
    if token != BOT_TOKEN:
        return {"ok": False, "error": "Invalid token"}
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"ok": False, "error": str(e)}
    return {"ok": True}

# Helper function to set the webhook
async def set_webhook():
    """Sets the webhook with Telegram"""
    url = f"{APP_URL}/webhook/{BOT_TOKEN}"
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": url}
    )
    if response.status_code == 200:
        logger.info(f"Webhook set successfully: {url}")
    else:
        logger.error(f"Failed to set webhook: {response.status_code} - {response.text}")

# Main function
if __name__ == "__main__":
    # Start the Telegram bot and set webhook asynchronously
    asyncio.run(set_webhook())
    # Run FastAPI app
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
