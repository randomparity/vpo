# ============================================================================
# VPO Container Image
# ============================================================================
# Multi-stage build for Video Policy Orchestrator with all dependencies
#
# Build:
#   docker build -t vpo:latest docker/vpo/
#
# Usage:
#   docker run --rm -v ~/Videos:/data vpo:latest scan /data
#   docker run --rm -v ~/Videos:/data vpo:latest inspect /data/movie.mkv
#   docker run --rm vpo:latest doctor
#
# ============================================================================

# ----------------------------------------------------------------------------
# Stage 1: Build VPO with Rust extension
# ----------------------------------------------------------------------------
FROM python:3.12.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install maturin for building the Rust extension
RUN pip install --no-cache-dir "maturin>=1.7,<2"

# Copy source code
WORKDIR /build
COPY . .

# Build the wheel
RUN maturin build --release --strip --out dist

# ----------------------------------------------------------------------------
# Stage 2: Runtime image
# ----------------------------------------------------------------------------
FROM python:3.12.11-slim AS runtime

# Labels
LABEL org.opencontainers.image.source="https://github.com/randomparity/vpo"
LABEL org.opencontainers.image.description="Video Policy Orchestrator - scan, organize, and transform video libraries"
LABEL org.opencontainers.image.licenses="MIT"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FFmpeg suite (includes ffprobe)
    ffmpeg \
    # MKVToolNix for container manipulation
    mkvtoolnix \
    # Minimal runtime libs
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy and install VPO wheel from builder
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash vpo
USER vpo

# Set up VPO data directory
ENV HOME=/home/vpo
WORKDIR /data

# Verify installation
RUN vpo --version && vpo doctor || true

# Default entrypoint
ENTRYPOINT ["vpo"]
CMD ["--help"]
