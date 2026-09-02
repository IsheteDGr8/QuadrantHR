FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chmod +x scripts/entrypoint.sh

EXPOSE 8080

HEALTHCHECK --interval=20s --timeout=5s --start-period=40s --retries=5 \
  CMD curl -f http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["./scripts/entrypoint.sh"]
