# ── Build stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Copy workspace definition first (layer cache)
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/
COPY backend/api/pyproject.toml backend/api/
COPY backend/worker/pyproject.toml backend/worker/
COPY evals/pyproject.toml evals/

# Install only production deps (no dev, no mlx extras)
RUN uv sync --frozen --no-dev --no-install-workspace

# Copy source
COPY core/src/ core/src/
COPY core/alembic/ core/alembic/
COPY backend/api/src/ backend/api/src/
COPY evals/src/ evals/src/

# Install workspace packages
RUN uv sync --frozen --no-dev

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# ffmpeg/ffprobe — the upload endpoint probes audio duration and stream type
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash blurt

COPY --from=builder --chown=blurt:blurt /app/.venv /app/.venv
COPY --from=builder --chown=blurt:blurt /app/core/src /app/core/src
COPY --from=builder --chown=blurt:blurt /app/core/alembic /app/core/alembic
COPY --from=builder --chown=blurt:blurt /app/backend/api/src /app/backend/api/src

USER blurt

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/core/src:/app/backend/api/src"

EXPOSE 8000

CMD ["uvicorn", "blurt_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
