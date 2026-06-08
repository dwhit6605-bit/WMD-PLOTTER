FROM python:3.11-slim

# System deps (none required beyond pip)
RUN apt-get update -q && apt-get install -y -q --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/  ./backend/
COPY frontend/ ./frontend/

WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -sf http://localhost:8000/api/health || exit 1

CMD ["python", "main.py"]
