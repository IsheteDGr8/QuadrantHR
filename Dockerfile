# Multi-stage Dockerfile for Ticket-Genie Monorepo

# Stage 1: FastAPI Backend Application
FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace:/workspace/backend

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN mkdir -p backend && touch backend/__init__.py \
    && pip install --no-cache-dir .[backend]

COPY backend/ ./backend/
COPY database/ ./database/
RUN pip install --no-cache-dir --no-deps . \
    && rm -rf build ticket_genie.egg-info

EXPOSE 8000

HEALTHCHECK CMD curl --fail http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 2: Svelte Vite Frontend Builder
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 3: Nginx Production Frontend
FROM nginx:alpine AS frontend

ENV PORT=80 \
    SERVER_NAME=localhost \
    BACKEND_URL=http://backend:8000

# Copy Nginx template for automatic envsubst environment dynamic configuration
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled Svelte production assets from builder stage
COPY --from=frontend-builder /app/dist /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK CMD wget --quiet --tries=1 --spider http://127.0.0.1:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]