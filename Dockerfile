# syntax=docker/dockerfile:1
FROM python:3.11-slim

# System deps that pandas/pyarrow sometimes need
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Default command runs the CLI; override with `bash` or different args as needed
ENTRYPOINT ["python", "-m", "cli.process"]