import os
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from pyppeteer import launch
import fitz  # PyMuPDF
from fastapi import FastAPI, Request
from telegram.ext.webhook import WebhookHandler
from uvicorn import run

# Bot token (use environment variable for security)
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-bot-token-here")  # Replace with your bot token if not using env vars

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

# FastAPI setup
app = FastAPI()

# Telegram bot setup
application = Application.builder().token(BOT_TOKEN).build()
handler = WebhookHandler(application)

# Function to convert HTML to PDF using Pyppeteer
async def convert_html_to_pdf(input_html, output_pdf):
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
            print("[ERROR] HTML content is empty!")
            return None

        await page.setContent(html_content)
        print("[DEBUG] Waiting for the page to load...")
        await page.waitForSelector('body')
        await asyncio.sleep(2)

        await page.pdf({'path': output_pdf, 'printBackground': True})
        print(f"[INFO] Full PDF saved at: {output_pdf}")
        return output_pdf
    except Exception as e:
        print(f"[ERROR] Error converting HTML to PDF: {e}")
        return None
    finally:
        if browser:
            await browser.close()

# Function to crop the first page of the generated PDF
def crop_pdf(input_pdf, output_pdf):
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
        print(f"[INFO] Cropped PDF saved at: {output_pdf}")
        pdf_document.close()
        cropped_pdf.close()
        return output_pdf
    except Exception as e:
        print(f"[ERROR] Error cropping PDF: {e}")
        return None

# Function to send the PDF to the user via Telegram bot
async def send_pdf_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, pdf_filename):
    try:
        with open(pdf_filename, "rb") as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_file,
                filename=os.path.basename(pdf_filename),
                caption="Here is your DL INFO."
            )
        print(f"PDF {pdf_filename} sent successfully!")
    except Exception as e:
        print(f"Failed to send PDF: {e}")
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
            os.remove(html_filename)
            os.remove(pdf_filename)
        else:
            await update.message.reply_text(f"❌ Failed to fetch details. HTTP Status: {response.status_code}")
    except Exception as e:
        await update.message.reply_text(f"⚠️ An error occurred: {str(e)}")

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dl_number))

# Webhook endpoint
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    await handler.handle_update(data)
    return {"status": "ok"}

# Main entry point
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    run(app, host="0.0.0.0", port=port)
