# Vera / AI HR Copilot — agent server (FastAPI)
# Build context: ClosedAI/
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv

COPY HRAgent_Main/ /app/
COPY hr_mcp /hr_mcp

RUN uv sync --frozen --no-dev || uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app:/hr_mcp

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -f http://127.0.0.1:8001/docs || exit 1

CMD ["python", "-m", "runtime.server", "--host", "0.0.0.0", "--port", "8001"]
