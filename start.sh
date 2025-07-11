#!/bin/bash
set -e

# Check BOT_TOKEN
if [ -z "$BOT_TOKEN" ]; then
  echo "BOT_TOKEN environment variable is not set."
  exit 1
fi

# Default PORT to 8080 if not set
if [ -z "$PORT" ]; then
  export PORT=8080
fi

# (Optional: Print the port)
echo "PORT is set to $PORT."

# Just run your app in the foreground so Render can manage it
exec python bot.py
