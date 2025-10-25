# Use the official Python base image
FROM python:3.11

# Set the working directory in the container
WORKDIR /app

# Copy your requirements file into the container
COPY requirements.txt .

# Install dependencies and Node.js5
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the ImageMagick policy patch script into the image
COPY patch_imagemagick_policy.sh /usr/local/bin/patch_imagemagick_policy.sh
RUN chmod +x /usr/local/bin/patch_imagemagick_policy.sh

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg imagemagick wget gnupg sqlite3 && \
    # Robustly patch ImageMagick policy to allow @ and TXT coders for MoviePy/TextClip
    for f in /etc/ImageMagick-*/policy.xml; do \
      if [ -f "$f" ]; then \
        sed -i 's|<policy domain="path" rights="none" pattern="@\\*"[ ]*/>|<!-- & -->|' "$f"; \
        sed -i 's|<policy domain="coder" rights="none" pattern="TXT"[ ]*/>|<!-- & -->|' "$f"; \
      fi; \
    done && \
    wget -q -O /usr/share/keyrings/google-chrome.gpg https://dl-ssl.google.com/linux/linux_signing_key.pub && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*



RUN apt-get update && apt-get install -y chromium chromium-driver

# Install cron for scheduled tasks
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Patch ImageMagick policy at build time for development
RUN /usr/local/bin/patch_imagemagick_policy.sh


# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app source code (including workers/) into the image
COPY . /app

# Prepare log file used by cron jobs
RUN touch /var/log/cron.log

# Copy and set entrypoint that patches policy (again at runtime) and runs cron in foreground
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
# Note: To run the API instead of cron, override entrypoint/cmd with:
#   uvicorn asgi:app --host 0.0.0.0 --port 8000

# For local dev inside the devcontainer, you can run both API and worker:
#   bash dev_start.sh