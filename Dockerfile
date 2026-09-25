# ── Frontend build stage ──────────────────────────────────────────────
FROM node:22-slim AS frontend-builder
WORKDIR /app/frontend-react
COPY frontend-react/package*.json ./
RUN npm install
COPY frontend-react/ ./
RUN npm run build

# ── Base stage ────────────────────────────────────────────────────────
FROM python:3.12-slim AS base
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy frontend build from builder
COPY --from=frontend-builder /app/frontend-react/dist ./backend/api/static/dist

# Create persistent directories
RUN mkdir -p backend/core backend/api/static/avatars

# ── API image ─────────────────────────────────────────────────────────
FROM base AS api
EXPOSE 8000
CMD ["python", "-m", "backend.api.uvicorn_runner"]

# ── Bot image ─────────────────────────────────────────────────────────
FROM base AS bot
CMD ["python", "backend/bot/main.py"]

