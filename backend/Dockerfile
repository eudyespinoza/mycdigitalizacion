FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock requirements-dev.lock .
RUN pip install --require-hashes -r requirements.lock
COPY . .

FROM base AS development
RUN pip install --require-hashes -r requirements-dev.lock

FROM base AS production-build
RUN APP_ENV=test DJANGO_DEBUG=false python manage.py collectstatic --noinput

FROM production-build AS production
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
