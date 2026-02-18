# Lobby - AI VTuber Recording & Streaming Software
# Multi-stage build for production deployment

# --- Stage 1: Frontend build ---
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Backend runtime ---
FROM python:3.11-slim AS runtime

# Install system dependencies (ffmpeg for video/audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Copy backend
COPY backend/ ./backend/
COPY config/ ./config/
COPY models/ ./models/

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create output directory
RUN mkdir -p /app/output

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the API server
CMD ["python", "-m", "backend.api.server"]
