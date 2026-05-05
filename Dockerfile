# Use Python 3.11 slim image for minimal footprint
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Install system dependencies for document processing
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (after dependencies to optimize caching)
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port 8000 for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Launch FastAPI server (Docker version with ChromaDB)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]