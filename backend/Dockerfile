FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

FROM base AS development
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

FROM base AS production
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
