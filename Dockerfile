# Multi-stage build for SQLQuiz application
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Add build arguments
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ARG VERSION=1.0.0

# Set as environment variables
ENV GIT_COMMIT=$GIT_COMMIT \
    BUILD_DATE=$BUILD_DATE \
    VERSION=$VERSION \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_APP=app.py \
    FLASK_ENV=production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy from builder stage
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application files
COPY --chown=appuser:appuser . .

# Ensure database directory exists and is writable
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Update PATH
ENV PATH=/home/appuser/.local/bin:$PATH

USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]