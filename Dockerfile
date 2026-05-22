FROM python:3.11-slim

# System deps for weasyprint (PDF) + lxml + curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 libffi-dev \
    libgdk-pixbuf-2.0-0 libcairo2 libglib2.0-0 libpangocairo-1.0-0 \
    curl build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn>=21.2

# Copy application code
COPY . .

# Ensure data directory exists with correct permissions
RUN mkdir -p /app/data && \
    useradd -m -u 1001 jobhunter && \
    chown -R jobhunter:jobhunter /app

USER jobhunter

EXPOSE 5055

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -sf http://localhost:5055/health || exit 1

# Gunicorn: 2 workers, gevent async, 120s timeout for long scrape tasks
CMD ["gunicorn", \
     "--bind", "0.0.0.0:5055", \
     "--workers", "2", \
     "--worker-class", "sync", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "api_server:app"]
