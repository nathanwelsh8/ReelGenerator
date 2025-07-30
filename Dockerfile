# Use the official Python base image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Copy your requirements file into the container
COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg imagemagick && \
    rm -rf /var/lib/apt/lists/*


# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Default command (optional, adjust as needed)
CMD ["python"]
