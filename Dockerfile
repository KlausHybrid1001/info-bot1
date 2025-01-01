# Use official Python image as base
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libjpeg-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    zlib1g-dev \
    wget \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the bot application code into the container
COPY . /app/

# Set the working directory
WORKDIR /app

# Expose the necessary port (use the dynamic port for Render)
EXPOSE 8080

# Command to run the FastAPI app with Uvicorn
CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8080"]
