# Build stage
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies with retry logic
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Production stage  
FROM python:3.11-slim-bookworm

# Install only runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user FIRST
RUN groupadd -r echoframe && useradd -r -g echoframe -m -u 1000 echoframe

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/echoframe/.local

# Fix ownership 
RUN chown -R echoframe:echoframe /home/echoframe/.local

WORKDIR /app
# Copy application code
COPY --chown=echoframe:echoframe . .

USER echoframe

# Make sure pip-installed scripts are available
ENV PATH=/home/echoframe/.local/bin:$PATH

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]