import os
import httpx
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from pyppeteer import launch
import fitz  # PyMuPDF
import logging
from urllib.parse import unquote
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN environment variable not set!")

CHROMIUM_PATH = "/usr/bin/chromium"
TMP_FOLDER = "/tmp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://sarathi.parivahan.gov.in/sarathiservice/relApplnSearch.do"
}

app = FastAPI()
application = Application.builder().token(BOT_TOKEN).build()

# --- PDF utilities (same as before) ---

async def convert_html_to_pdf(input_html, output_pdf):
    browser = None
    try:
        browser = await launch(
            headless=True,
            executablePath=CHROMIUM_PATH,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--single-process',
                '--disable-dev-shm-usage'
            ]
        )
        page = await browser.newPage()
        with open(input_html, 'r', encoding='utf-8') as f:
            html_content = f.read()
        await page.setContent(html_content)
        await page.waitForSelector('body')
        await asyncio.sleep(1)
        await page.pdf({'path': output_pdf, 'printBackground': True, 'format': 'Legal'})
        return output_pdf
    except Exception as e:
        logger.error(f"Error converting HTML to PDF: {e}")
        return None
    finally:
        if browser:
            await browser.close()

def crop_pdf(input_pdf, output_pdf):
    try:
        pdf_document = fitz.open(input_pdf)
        first_page = pdf_document.load_page(0)
        crop_top = 120
        crop_bottom = 50
        crop_rect = fitz.Rect(0, crop_top, first_page.rect.width, first_page.rect.height - crop_bottom)
        first_page.set_cropbox(crop_rect)
        cropped_pdf = fitz.open()
        cropped_pdf.insert_pdf(pdf_document, from_page=0, to_page=0)
        cropped_pdf.save(output_pdf)
        pdf_document.close()
        cropped_pdf.close()
        return output_pdf
    except Exception as e:
        logger.error(f"Error cropping PDF: {e}")
        return None

# --- Telegram handlers ---

async def send_pdf_to_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE, pdf_filename):
    try:
        with open(pdf_filename, "rb") as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=pdf_file,
                filename=os.path.basename(pdf_filename),
                caption="Here is your DL INFO."
            )
    except Exception as e:
        logger.error(f"Failed to send PDF: {e}")
        await update.message.reply_text("Failed to send the PDF file. Please try again.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Send your DL number (any format, e.g. 'AB12 1234567890') to get the PDF. "
        "I'll try to fetch your info regardless of format."
    )

async def handle_dl_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dl_number = update.message.text.upper().strip()
    dl_number = ' '.join(dl_number.split())

    soft_pattern = r'^[A-Z]{2}\d{2} \d{5,}$'
    if not re.match(soft_pattern, dl_number):
        await update.message.reply_text(
            "ℹ️ Note: DL numbers are usually formatted like 'AB12 1234567890' (two letters, two numbers, space, then more numbers), but formats may vary by state. I'll try anyway!"
        )

    html_filename = os.path.join(TMP_FOLDER, f"{dl_number}_details.html")
    pdf_filename = os.path.join(TMP_FOLDER, f"{dl_number}_details.pdf")
    cropped_pdf_filename = os.path.join(TMP_FOLDER, f"{dl_number}_cropped.pdf")
    url = f"https://sarathi.parivahan.gov.in/sarathiservice/dlDetailsResult.do?reqDlNumber={dl_number}"

    try:
        await update.message.reply_text(f"⏳ Fetching DL details for {dl_number}. Please wait...")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=HEADERS)
        if response.status_code == 200 and "<title>" in response.text:
            with open(html_filename, "w", encoding="utf-8") as file:
                file.write(response.text)
            await convert_html_to_pdf(html_filename, pdf_filename)
            crop_pdf(pdf_filename, cropped_pdf_filename)
            await send_pdf_to_telegram(update, context, cropped_pdf_filename)
        else:
            await update.message.reply_text("❌ Failed to fetch details or invalid response.")
    except Exception as e:
        logger.error(f"Error processing DL number: {e}")
        await update.message.reply_text(f"⚠️ An error occurred: {str(e)}")
    finally:
        # Clean up all files!
        for fname in [html_filename, pdf_filename, cropped_pdf_filename]:
            try:
                if os.path.exists(fname):
                    os.remove(fname)
            except Exception:
                pass

# --- Webhook for Telegram ---
@app.post("/webhook/{bot_token}")
async def webhook(bot_token: str, request: Request):
    decoded_token = unquote(bot_token)
    if (decoded_token != BOT_TOKEN):
        return {"status": "error", "message": "Invalid bot token"}
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return {"ok": False, "error": str(e)}
    return {"ok": True}

# --- Uptime health check ---
@app.api_route("/keepalive", methods=["GET", "HEAD"])
async def keepalive():
    return {"status": "ok"}

# --- WEB FORM & PDF DOWNLOAD ---
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
      <head>
        <title>DL PDF Download</title>
        <style>
          body { font-family: Arial; background:#f7f7fa; padding:2em;}
          form { background:white; padding:2em; border-radius:8px; box-shadow:0 1px 4px #ccc; max-width:400px; margin:auto;}
          input[type='text'] { width:92%; padding:0.5em; }
          input[type='submit'] { padding:0.5em 1.5em; font-size:1em; margin-top:1em; }
        </style>
      </head>
      <body>
        <h2 style="text-align:center;">Driving License PDF Download</h2>
        <form action="/webdl" method="get">
          <label for="dl">Enter DL Number:</label><br>
          <input type="text" name="dl" id="dl" required placeholder="e.g. AB12 1234567890"><br>
          <input type="submit" value="Get PDF">
        </form>
        <p style="text-align:center; color:#888; margin-top:2em;">
          Example: <b>MH47 20210040286</b> or <b>AB12 1234567890</b>
        </p>
      </body>
    </html>
    """

@app.get("/webdl")
async def web_dl(dl: str):
    dl_number = dl.upper().strip()
    dl_number = ' '.join(dl_number.split())
    soft_pattern = r'^[A-Z]{2}\d{2} \d{5,}$'
    html_filename = os.path.join(TMP_FOLDER, f"{dl_number}_details.html")
    pdf_filename = os.path.join(TMP_FOLDER, f"{dl_number}_details.pdf")
    cropped_pdf_filename = os.path.join(TMP_FOLDER, f"{dl_number}_cropped.pdf")
    url = f"https://sarathi.parivahan.gov.in/sarathiservice/dlDetailsResult.do?reqDlNumber={dl_number}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=HEADERS)
        if response.status_code == 200 and "<title>" in response.text:
            with open(html_filename, "w", encoding="utf-8") as file:
                file.write(response.text)
            await convert_html_to_pdf(html_filename, pdf_filename)
            crop_pdf(pdf_filename, cropped_pdf_filename)
            return FileResponse(
                cropped_pdf_filename,
                media_type="application/pdf",
                filename=f"{dl_number}_DL.pdf"
            )
        else:
            return HTMLResponse(
                "<b>❌ Failed to fetch details or invalid response.</b>", status_code=400)
    except Exception as e:
        logger.error(f"Web DL error: {e}")
        return HTMLResponse(
            f"<b>⚠️ Error occurred: {str(e)}</b>", status_code=500)
    finally:
        # Clean up temp files except for the file being sent (will be deleted after response)
        for fname in [html_filename, pdf_filename]:
            try:
                if os.path.exists(fname):
                    os.remove(fname)
            except Exception:
                pass

# --- Startup event: set webhook for Telegram bot ---
@app.on_event("startup")
async def on_startup():
    webhook_url = f"https://info-bot1-1.onrender.com/webhook/{BOT_TOKEN}"
    try:
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dl_number))
        await application.initialize()
        await application.bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
