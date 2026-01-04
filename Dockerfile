# syntax=docker/dockerfile:1.4
# Multi-stage build for Fall Detection System
# 優化重點: 最大化 layer cache 利用率

# ============================================================
# Stage 1: Builder - 安裝依賴
# ============================================================
FROM python:3.12-slim AS builder

# Install build dependencies (合併成單一 layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# 關鍵優化: 先複製依賴定義檔，觸發依賴快取
# 只有 pyproject.toml 或 uv.lock 改動才會重新安裝依賴
COPY pyproject.toml uv.lock ./

# 建立空的 README.md (hatchling 需要) 避免依賴變化
RUN touch README.md

# 安裝依賴 (這層會被快取，除非 pyproject.toml/uv.lock 改動)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ============================================================
# Stage 2: Runtime - 最小化映像
# ============================================================
FROM python:3.12-slim AS runtime

# Install runtime dependencies for OpenCV (單一 layer)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    libgstreamer1.0-0 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user and directories (單一 layer)
RUN useradd -m -u 1000 fds && \
    mkdir -p /app/data /app/config /app/logs && \
    chown -R fds:fds /app

WORKDIR /app

# Copy virtual environment from builder (這層很大但會被快取)
COPY --from=builder /app/.venv /app/.venv

# 關鍵: 最後才複製應用程式碼，讓程式碼改動不影響依賴層
COPY --chown=fds:fds src/ ./src/
COPY --chown=fds:fds scripts/ ./scripts/
COPY --chown=fds:fds main.py pyproject.toml README.md ./
COPY --chown=fds:fds config/ ./config/
# YOLO11 models (download before build or let Ultralytics auto-download at runtime)
# Models: yolo11n.pt (BBox), yolo11s-pose.pt (Pose)
COPY --chown=fds:fds yolo11*.pt ./

# Switch to non-root user
USER fds

# Environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose web dashboard port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/status || python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "main.py"]
