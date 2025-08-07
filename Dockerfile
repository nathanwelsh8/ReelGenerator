# Use the official Python base image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy your requirements file into the container
COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg imagemagick wget gnupg && \
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y chromium chromium-driver

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Default command (optional, adjust as needed)
CMD ["python"]