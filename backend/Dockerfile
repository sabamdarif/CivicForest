# syntax=docker/dockerfile:1
FROM python:3.14-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local

# uv gives us fast, reproducible installs from pyproject + uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependency layer — cached until pyproject/lock change.
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-install-project --no-dev || uv pip install -r pyproject.toml

COPY . .

EXPOSE 8000

# Default command is overridden per-service in docker-compose (web vs worker vs beat).
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]
