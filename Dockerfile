# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Manim
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2-dev \
    ffmpeg \
    texlive \
    texlive-latex-extra \
    texlive-fonts-extra \
    texlive-latex-recommended \
    texlive-science \
    tipa \
    libpango1.0-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml README.md .

# Install Python dependencies using uv
RUN uv pip install --system .

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p media public

# Expose port 5000
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=src/main.py
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Run the application
CMD ["python", "src/main.py"]
