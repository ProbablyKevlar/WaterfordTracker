# Dockerfile for Waterford Track & Field Dashboard
# Optimized for Synology NAS Container Manager with persistent external volume mounting

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    DB_DIR=/app/data \
    DB_PATH=/app/data/waterford_tracker.db

# Install system dependencies (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create persistent data volume mount point
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# Copy application files and logo
COPY database.py auth.py milesplit_sync.py app.py Waterford-Halfmoon.webp ./

# Expose Streamlit default port
EXPOSE 8501

# Healthcheck to verify app is serving
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Start Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
