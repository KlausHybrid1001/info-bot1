#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Set the environment variable for the Telegram bot token
export BOT_TOKEN="7597041420:AAGxS7T7fnwenj1FvlpR1bEl5niRm_tCAzU"

# Set the Telegram webhook
echo "Setting Telegram Webhook..."
WEBHOOK_URL="https://info-bot1-1.onrender.com/webhook/$BOT_TOKEN"
RESPONSE=$(curl -s -w "%{http_code}" -o /dev/null "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=$WEBHOOK_URL")

if [ "$RESPONSE" -eq 200 ]; then
  echo "Webhook set successfully"
else
  echo "Failed to set webhook. HTTP status code: $RESPONSE"
  exit 1
fi

# Start the Python bot
echo "Starting Python bot..."
python bot.py
