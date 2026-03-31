
FROM python:3.9-slim
 
# -----------------------------
# Install dependencies
# -----------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    pip install --no-cache-dir requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
 
# -----------------------------
# Set working directory
# -----------------------------
WORKDIR /app
 
# -----------------------------
# Copy the application
# -----------------------------
COPY red_alert.py .
 
# -----------------------------
# HEALTHCHECK:
# Check OREF endpoint directly.
# If unreachable → container is unhealthy.
# -----------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fs https://www.oref.org.il/WarningMessages/alert/alerts.json || exit 1
 
# -----------------------------
# Run the alert listener
# -----------------------------
CMD ["python", "-u", "red_alert.py"]
