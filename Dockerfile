# ── Build stage ────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ ./backend/

# Create persistent directories
RUN mkdir -p backend/core backend/api/static/avatars backend/api/overlay_configs

# ── API image ─────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Bot image ─────────────────────────────────────────────────────────
FROM base AS bot
CMD ["python", "backend/bot/main.py"]
