# Railway Dockerfile for Drew Meme Generator
FROM python:3.12-slim

# Install system dependencies for OpenCV and InsightFace
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for models and static files
RUN mkdir -p /app/models /app/static

# Expose port (Railway will set $PORT)
EXPOSE 8080

# Start command
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
