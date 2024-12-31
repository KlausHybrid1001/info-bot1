import os
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from pyppeteer import launch
import fitz  # PyMuPDF
from fastapi import FastAPI, Request
import logging
from uvicorn import run

# Hardcoded for testing (replace with secure methods in production)
BOT_TOKEN = "7597041420:AAGxS7T7fnwenj1FvlpR1bEl5niRm_tCAzU"  # Replace with your token
APP_URL = "https://info-bot1-1.onrender.com"  # Replace with your Render app's public URL
CHROMIUM_PATH = "/usr/bin/chromium"  # Path to Chromium binary
tmp_folder = "/tmp"  # Temporary folder for files
output_folder = "/tmp"  # Output folder for cropped PDFs

# Initialize FastAPI app and Telegram bot application
app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to convert HTML to PDF using Pyppeteer
async def convert_html_to_pdf(input_html, output_pdf):
    browser = None
    try:
        browser = await launch(
            headless=True,
            executablePath=CHROMIUM_PATH,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.newPage()
        with open(input_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        await page.setContent(html_content)
        await asyncio.sleep(2)  # Allow page to render
        await page.pdf({'path': output_pdf, 'printBackground': True})
        return output_pdf
    except Exception as e:
        logger.error(f"[ERROR] Error converting HTML to PDF: {e}")
        return None
    finally:
        if browser:
            await browser.close()

# Function to crop the first page of the generated PDF
def crop_pdf(input_pdf, output_pdf):
    try:
        pdf_document = fitz.open(input_pdf)
        first_page = pdf_document[0]
        crop_rect = fitz.Rect(0, 165, first_page.rect.width, first_page.rect.height - 5)
        first_page.set_cropbox(crop_rect)
        cropped_pdf = fitz.open()
        cropped_pdf.insert_pdf(pdf_document, from_page=0, to_page=0)
        cropped_pdf.save(output_pdf)
        pdf_document.close()
        cropped_pdf.close()
        return output_pdf
    except Exception as e:
        logger.error(f"[ERROR] Error cropping PDF: {e}")
        return None

# Function to send the PDF to the user via Telegram bot
async def send_pdf_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, pdf_filename):
    try:
        with open(pdf_filename, "rb") as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_file,
                filename=os.path.basename(pdf_filename),
                caption="Here is your DL info."
            )
    except Exception as e:
        logger.error(f"Failed to send PDF: {e}")
        await update.message.reply_text("Failed to send the PDF file. Please try again.")

# Start command to welcome users
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome! Send the DL number directly to get the PDF.")

# Message handler for DL number input
async def handle_dl_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dl_number = update.message.text.strip()
    if not dl_number:
        await update.message.reply_text("❌ Please provide a valid DL number.")
        return

    html_filename = os.path.join(tmp_folder, f"{dl_number}_details.html")
    pdf_filename = os.path.join(tmp_folder, f"{dl_number}_details.pdf")
    cropped_pdf_filename = os.path.join(output_folder, f"{dl_number}_cropped.pdf")

    if os.path.exists(cropped_pdf_filename):
        await update.message.reply_text("✅ PDF already exists. Sending the existing file...")
        await send_pdf_to_telegram(update, context, cropped_pdf_filename)
        return

    url = f"https://sarathi.parivahan.gov.in/sarathiservice/dlDetailsResult.do?reqDlNumber={dl_number}"
    try:
        await update.message.reply_text(f"⏳ Fetching DL details for {dl_number}. Please wait...")
        response = requests.get(url)
        if response.status_code == 200:
            with open(html_filename, "w", encoding="utf-8") as file:
                file.write(response.text)
            pdf_filename = await convert_html_to_pdf(html_filename, pdf_filename)
            if not pdf_filename:
                await update.message.reply_text("❌ Error converting HTML to PDF.")
                return
            cropped_pdf_filename = crop_pdf(pdf_filename, cropped_pdf_filename)
            if not cropped_pdf_filename:
                await update.message.reply_text("❌ Error cropping the PDF.")
                return
            await send_pdf_to_telegram(update, context, cropped_pdf_filename)
            os.remove(html_filename)
            os.remove(pdf_filename)
        else:
            await update.message.reply_text(f"❌ Failed to fetch details. HTTP Status: {response.status_code}")
    except Exception as e:
        logger.error(f"[ERROR] {e}")
        await update.message.reply_text("⚠️ An error occurred. Please try again.")

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dl_number))

# Webhook endpoint to receive updates
@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
        await application.update_queue.put(Update.de_json(update, application.bot))
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"status": "error", "message": str(e)}

# Health check endpoint
@app.get("/")
async def root():
    return {"status": "ok"}

# Set webhook function
async def set_webhook():
    url = f"{APP_URL}/webhook/{BOT_TOKEN}"
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={"url": url},
    )
    if response.status_code == 200:
        logger.info(f"Webhook set successfully: {url}")
    else:
        logger.error(f"Failed to set webhook: {response.status_code} - {response.text}")

# Main entry point
if __name__ == "__main__":
    asyncio.run(set_webhook())
    port = int(os.getenv("PORT", 8080))
    run(app, host="0.0.0.0", port=port)
