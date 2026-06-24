# =============================================================================
# Tovbase — Multi-stage Dockerfile for FastAPI backend
# =============================================================================
# Build:  docker build -t tovbase-api .
# Run:    docker run -p 8001:8001 --env-file .env tovbase-api
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder — install dependencies into a virtual env
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for building psycopg2-binary and numpy
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy only dependency metadata first (layer cache optimisation)
COPY pyproject.toml ./

# Create venv and install production dependencies (no dev extras)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# ---------------------------------------------------------------------------
# Stage 2: Runtime — slim image with only what we need
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# Minimal runtime deps (libpq for psycopg2, curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application code only (no web/, extension/, tests/)
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY pyproject.toml ./

# Non-root user for security
RUN groupadd --gid 1000 tovbase && \
    useradd --uid 1000 --gid tovbase --create-home tovbase && \
    chown -R tovbase:tovbase /app
USER tovbase

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
