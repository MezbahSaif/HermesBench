# Multi-stage build for Streamlit Dashboard
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed during build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        pkg-config \
        && rm -rf /var/lib/apt/lists/*

# Install Python packages in builder stage
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install cron (for background scheduling support)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cron \
        curl \
        && rm -rf /var/lib/apt/lists/* \
        && mkdir -p /data/logs \
        && chown -R appuser:appuser /data

# Create non-root user for running the application
RUN useradd --create-home --shell /bin/bash appuser

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY --chown=appuser:appuser config.yaml /app/config.yaml
COPY --chown=appuser:appuser logger_config.py /app/logger_config.py
COPY --chown=appuser:appuser worker.py /app/worker.py

# Create data directories
RUN mkdir -p /data/logs /data/output \
    && chown -R appuser:appuser /data

EXPOSE 8501

USER appuser

ENTRYPOINT ["/entrypoint.sh"]
