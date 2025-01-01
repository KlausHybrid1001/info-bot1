#!/bin/bash

# Set the Telegram webhook
echo "Setting Telegram Webhook..."
curl -s "https://api.telegram.org/bot7597041420:AAGxS7T7fnwenj1FvlpR1bEl5niRm_tCAzU/setWebhook?url=https://info-bot1-1.onrender.com/webhook/7597041420:AAGxS7T7fnwenj1FvlpR1bEl5niRm_tCAzU"

# Start the Python bot
echo "Starting Python bot..."
python bot.py
