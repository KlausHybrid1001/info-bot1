import os
import requests
import asyncio
from fastapi import FastAPI, Request
import uvicorn
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from pyppeteer import launch
import fitz  # PyMuPDF
import logging
from urllib.parse import unquote
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Your bot token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable not set!")

# Path to the locally installed Chromium executable
CHROMIUM_PATH = "/usr/bin/chromium"  # Render uses a default Chromium installation

# Directory paths
tmp_folder = "/tmp"  # Use /tmp directory for temporary files
output_folder = "/tmp"  # Store output PDFs in /tmp (temporary storage)

# HTTP headers and cookies
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://sarathi.parivahan.gov.in/sarathiservice/relApplnSearch.do",
    "Cookie": "JSESSIONID=3899D603FD2EACF9C7678AEB5152EE12; _ga_W8LPQ3GPJF=deleted; _gid=GA1.3.2141960273.1735205718; GOTWL_MODE=2; _ga=GA1.1.1181027328.1735205717; STATEID=dklEcFJuUWtUd2FTYjdINVBvMDhJdz09"
}

# FastAPI app
app = FastAPI()

# Telegram Application instance
application = Application.builder().token(BOT_TOKEN).build()

# Function to initialize the bot and add handlers
async def initialize_bot():
    logger.info("Initializing the bot and adding handlers")
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dl_number))
    await application.initialize()
    logger.info("Bot initialized")

# Function to convert HTML to PDF using Pyppeteer
async def convert_html_to_pdf(input_html, output_pdf):
    logger.info("Converting HTML to PDF")
    browser = None
    try:
        # Launch Chromium
        browser = await launch(
            headless=True,
            executablePath=CHROMIUM_PATH,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        page = await browser.newPage()

        with open(input_html, 'r', encoding='utf-8') as f:
            html_content = f.read()

        if not html_content:
            logger.error("HTML content is empty!")
            return None

        await page.setContent(html_content)
        logger.info("Waiting for the page to load...")
        await page.waitForSelector('body')
        await asyncio.sleep(2)

        await page.pdf({'path': output_pdf, 'printBackground': True})
        logger.info(f"Full PDF saved at: {output_pdf}")
        return output_pdf
    except Exception as e:
        logger.error(f"Error converting HTML to PDF: {e}")
        return None
    finally:
        if browser:
            await browser.close()

# Function to crop the first page of the generated PDF
def crop_pdf(input_pdf, output_pdf):
    logger.info("Cropping PDF")
    try:
        pdf_document = fitz.open(input_pdf)
        first_page = pdf_document.load_page(0)
        page_height = first_page.rect.height
        crop_top = 165
        crop_bottom = 5

        crop_rect = fitz.Rect(0, crop_top, first_page.rect.width, page_height - crop_bottom)
        first_page.set_cropbox(crop_rect)

        cropped_pdf = fitz.open()
        cropped_pdf.insert_pdf(pdf_document, from_page=0, to_page=0)
        cropped_pdf.save(output_pdf)
        logger.info(f"Cropped PDF saved at: {output_pdf}")
        pdf_document.close()
        cropped_pdf.close()
        return output_pdf
    except Exception as e:
        logger.error(f"Error cropping PDF: {e}")
        return None

# Function to send the PDF to the user via Telegram bot
async def send_pdf_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, pdf_filename):
    logger.info("Sending PDF to Telegram")
    try:
        with open(pdf_filename, "rb") as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_file,
                filename=os.path.basename(pdf_filename),
                caption="Here is your DL INFO."
            )
        logger.info(f"PDF {pdf_filename} sent successfully!")
    except Exception as e:
        logger.error(f"Failed to send PDF: {e}")
        await update.message.reply_text("Failed to send the PDF file. Please try again.")

# Start command to welcome users
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text("Welcome! Send the DL number directly to get the PDF.")

# Message handler for DL number input
async def handle_dl_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received DL number: {update.message.text}")
    dl_number = update.message.text.strip()

    # Validate the DL number format
    if not re.match(r'^[A-Z]{2}\d{2} \d+$', dl_number):
        await update.message.reply_text("❌ Invalid DL number format. Please provide a DL number in the format: MH02 19870039492")
        return

    html_filename = os.path.join(tmp_folder, f"{dl_number}_details.html")
    pdf_filename = os.path.join(tmp_folder, f"{dl_number}_details.pdf")
    cropped_pdf_filename = os.path.join(output_folder, f"{dl_number}_cropped.pdf")

    url = f"https://sarathi.parivahan.gov.in/sarathiservice/dlDetailsResult.do?reqDlNumber={dl_number}"

    try:
        await update.message.reply_text(f"⏳ Fetching DL details for {dl_number}. Please wait...")
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            with open(html_filename, "w", encoding="utf-8") as file:
                file.write(response.text)

            pdf_filename = await convert_html_to_pdf(html_filename, pdf_filename)
            if pdf_filename is None:
                await update.message.reply_text("❌ Error converting HTML to PDF.")
                return

            cropped_pdf_filename = crop_pdf(pdf_filename, cropped_pdf_filename)
            if cropped_pdf_filename is None:
                await update.message.reply_text("❌ Error cropping the PDF.")
                return

            await send_pdf_to_telegram(update, context, cropped_pdf_filename)

            # Clean up temporary files
            logger.info(f"Removing temporary files: {html_filename} and {pdf_filename}")
            os.remove(html_filename)
            os.remove(pdf_filename)
            logger.info("Temporary files removed successfully")
        else:
            await update.message.reply_text(f"❌ Failed to fetch details. HTTP Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Error processing DL number: {e}")
        await update.message.reply_text(f"⚠️ An error occurred: {str(e)}")

# Webhook handler
@app.post("/webhook/{bot_token}")
async def webhook(bot_token: str, request: Request):
    # Decode the bot token to handle URL-encoded characters
    decoded_token = unquote(bot_token)
    logging.info(f"Decoded bot token: {decoded_token}")

    # Compare the decoded token
    if decoded_token != BOT_TOKEN:
        logging.error("Invalid bot token")
        return {"status": "error", "message": "Invalid bot token"}

    try:
        data = await request.json()
        logging.info(f"Received update: {data}")
        
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        logging.error(f"Error processing webhook: {e}")
        return {"ok": False, "error": str(e)}
    
    return {"ok": True}

# Keep-alive endpoint
@app.get("/keepalive")
async def keepalive():
    return {"status": "ok"}

# Function to run the keep-alive mechanism
async def keep_alive():
    url = "https://info-bot1-1.onrender.com/keepalive"
    interval = 300  # 5 minutes

    while True:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                logger.info("Keep-alive request successful")
            else:
                logger.warning(f"Keep-alive request failed with status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending keep-alive request: {e}")

        await asyncio.sleep(interval)

# Set webhook on startup
@app.on_event("startup")
async def on_startup():
    webhook_url = f"https://info-bot1-1.onrender.com/webhook/{BOT_TOKEN}"
    try:
        await initialize_bot()  # Initialize the bot and add handlers
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

    # Run the keep-alive mechanism concurrently
    asyncio.create_task(keep_alive())

# Main entry point
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
