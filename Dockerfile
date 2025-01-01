# Use official Python image as base
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \                        # Essential packages for building software
    python3-dev \                            # Python development tools
    libjpeg-dev \                            # JPEG library
    liblcms2-dev \                           # Little CMS color management library
    libopenjp2-7-dev \                       # OpenJPEG library
    zlib1g-dev \                             # Compression library
    wget \                                   # Network downloader
    ca-certificates \                        # Common CA certificates
    fonts-liberation \                       # Liberation fonts
    libappindicator3-1 \                     # Application indicators
    libasound2 \                             # ALSA sound library
    libatk-bridge2.0-0 \                     # ATK accessibility toolkit
    libatk1.0-0 \                            # ATK accessibility toolkit
    libcups2 \                               # Common Unix Printing System client library
    libdbus-1-3 \                            # D-Bus message bus library
    libgdk-pixbuf2.0-0 \                     # GDK Pixbuf library
    libnspr4 \                               # Netscape Portable Runtime library
    libnss3 \                                # Network Security Services libraries
    libx11-xcb1 \                            # X11 XCB library
    libxcomposite1 \                         # Composite extension library
    libxdamage1 \                            # Damage extension library
    libxrandr2 \                             # X RandR extension library
    xdg-utils \                              # Utilities for the X Desktop Group
    chromium \                               # Chromium browser
    && rm -rf /var/lib/apt/lists/*           # Clean up APT when done

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
