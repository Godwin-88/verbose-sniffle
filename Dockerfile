FROM python:3.11-slim

# System deps for weasyprint (PDF export) + lxml + Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libharfbuzz0b libfontconfig1 libffi-dev \
    libgdk-pixbuf-2.0-0 libcairo2 libglib2.0-0 \
    curl build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user for security
RUN useradd -m -u 1001 jobhunter && chown -R jobhunter:jobhunter /app
USER jobhunter

EXPOSE 5055

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -sf http://localhost:5055/health || exit 1

CMD ["python", "api_server.py"]
