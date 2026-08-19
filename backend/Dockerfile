FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock requirements-dev.lock .
RUN pip install --require-hashes -r requirements.lock
COPY . .

FROM base AS development
RUN pip install --require-hashes -r requirements-dev.lock

FROM base AS production-build
ENV APP_ENV=production \
    DJANGO_DEBUG=false \
    DJANGO_SECRET_KEY=container-build-signing-key-that-is-not-a-placeholder \
    POSTGRES_PASSWORD=container-build-database-password-not-a-placeholder \
    SITE_ADDRESS=build.example.test \
    DJANGO_ALLOWED_HOSTS=build.example.test
RUN python manage.py collectstatic --noinput

FROM production-build AS production
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
