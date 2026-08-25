# ── Build stage ─────────────────────────────────────────────────────────────
# Use a slim Python 3.12 image as the base.
FROM python:3.12-slim

# Prevents Python from writing .pyc files and ensures stdout/stderr are
# flushed immediately (important for Cloud Run log streaming).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a non-root user for security best practice on Cloud Run.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Install dependencies first (better layer caching — only re-runs when
# requirements.txt changes, not on every code change).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code.
COPY . .

# Hand ownership to the non-root user.
RUN chown -R appuser:appgroup /app
USER appuser

# Cloud Run injects the PORT environment variable at runtime.
# gunicorn reads $PORT via shell expansion — do NOT hardcode a port number.
CMD exec gunicorn \
        --bind "0.0.0.0:${PORT:-8080}" \
        --workers 2 \
        --threads 4 \
        --timeout 0 \
        app:app
