# ======================================================
# Dockerfile — Production Multi-Stage Container Build
# ======================================================
# SYSTEM DESIGN CONCEPT: Multi-Stage Builds & Minimal Containers
# -------------------------------------------------
# 1. WHY MULTI-STAGE BUILDS?
#    - Stage 1 (Builder): Compiles C-extensions and wheels (includes build tools, gcc, headers).
#    - Stage 2 (Runner): Copies only the final Python wheels and source code into a clean,
#      slim base image.
#    - BENEFITS:
#      - Image size shrinks by 60-80% (~120MB vs ~800MB)
#      - Security: Compilers and build tools are NOT present in production,
#        drastically reducing the attack surface.
#
# 2. NON-ROOT USER:
#    - Running containers as `root` is a major security vulnerability.
#    - We create and run as a dedicated `appuser` (Principle of Least Privilege).
# ======================================================

# --- Stage 1: Build Dependencies ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies to wheels directory
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# --- Stage 2: Final Production Runner ---
FROM python:3.11-slim AS runner

WORKDIR /app

# Create a non-privileged user and group
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -s /bin/sh appuser

# Copy installed python packages from builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy application source code
COPY --chown=appuser:appgroup . .

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_NAME=url-shortener

# Switch to non-root user
USER appuser

# Expose internal FastAPI port
EXPOSE 8000

# Run uvicorn with standard production settings
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
