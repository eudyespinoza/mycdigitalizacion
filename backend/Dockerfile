FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home appuser
COPY requirements.lock requirements-dev.lock .
RUN pip install --require-hashes -r requirements.lock
COPY --chown=appuser:appuser . .

FROM base AS development
RUN pip install --require-hashes -r requirements-dev.lock

FROM base AS production-build
RUN chown appuser:appuser /app
USER appuser
RUN APP_ENV=test DJANGO_DEBUG=false python manage.py collectstatic --noinput

FROM production-build AS production
