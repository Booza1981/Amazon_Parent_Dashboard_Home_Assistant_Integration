# Amazon Parental Dashboard to Home Assistant Integration
# Docker image for running as a daemon service

FROM python:3.13-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for cookies (will be mounted as volume)
RUN mkdir -p /app/amazon_parental

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Install Playwright browsers as appuser so they're in the user's home directory
RUN playwright install chromium

# Install system dependencies as root (need to go back to root temporarily)
USER root
RUN playwright install-deps chromium

# Switch back to appuser
USER appuser

# Environment variables (can be overridden in docker-compose.yml or at runtime)
ENV MQTT_BROKER="localhost"
ENV MQTT_PORT="1883"
ENV MQTT_USERNAME=""
ENV MQTT_PASSWORD=""
ENV CHILD_NAME="daughter"
ENV SYNC_INTERVAL="300"

# Disable Python buffering so logs appear immediately in docker logs
ENV PYTHONUNBUFFERED=1
ENV SETUP_MODE="false"

# Expose web UI port for cookie authentication
EXPOSE 8080

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
USER root
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
USER appuser

# Run via entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
