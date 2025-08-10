# Use the official Python base image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy your requirements file into the container
COPY requirements.txt .

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
    wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*


RUN apt-get update && apt-get install -y chromium chromium-driver

# Patch ImageMagick policy at build time for development
RUN /usr/local/bin/patch_imagemagick_policy.sh

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

CMD ["/bin/bash", "/usr/local/bin/patch_imagemagick_policy.sh"]