# Active Recall — Dockerfile
# Build context: project root (ACTIVE RECALL/)
FROM python:3.11-slim

# System deps for Kokoro (espeak-ng), Piper, soundfile, and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng-dev \
    libsndfile1 \
    libsndfile1-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY BACKEND/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY BACKEND/ ./BACKEND/

# Copy frontend (served as static files from /app route)
COPY TEST-APP/ ./TEST-APP/

# Model cache directories (mounted as volumes in production)
RUN mkdir -p /root/.cache/huggingface /app/BACKEND/.piper_models

WORKDIR /app/BACKEND

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# 2 workers: uno atiende requests mientras el otro vectoriza/ingesta en background.
# Con run_in_executor en vectorizer.py el event loop nunca se bloquea.
# RAM: ~165MB/worker × 2 = ~330MB sobre 956MB disponibles — seguro.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
