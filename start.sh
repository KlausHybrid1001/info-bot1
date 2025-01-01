#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Set the environment variable for the Telegram bot token
export BOT_TOKEN="7597041420:AAGxS7T7fnwenj1FvlpR1bEl5niRm_tCAzU"

# Ensure the PORT environment variable is set
if [ -z "$PORT" ]; then
  echo "PORT environment variable is not set. Using default port 8080."
  export PORT=8080
else
  echo "PORT environment variable is set to $PORT."
fi

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

# Start the Python bot in the background and redirect output to log file
echo "Starting Python bot..."
nohup python bot.py > bot.log 2>&1 &

# Start the keep-alive script in the background and redirect output to log file
echo "Starting keep-alive script..."
nohup python keep_alive.py > keep_alive.log 2>&1 &

# Wait for both background processes to finish
wait
