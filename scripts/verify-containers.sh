#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  rm -f "${static_asset:-}"
  docker compose --env-file .env.example down --volumes --remove-orphans || true
  docker compose -f compose.prod.yaml down --volumes --remove-orphans || true
}
trap cleanup EXIT

export POSTGRES_DB=mycdigitalizacion_ci
export POSTGRES_USER=mycdigitalizacion_ci
export POSTGRES_PASSWORD=ci-database-password-not-for-production
export REDIS_PASSWORD=ci-redis-password-not-for-production
export DJANGO_SECRET_KEY=ci-signing-key-not-for-production-and-long-enough
export PERSONAL_DATA_ENCRYPTION_KEY=ci-personal-data-key-not-for-production
export RELEASE_ID=ci-release-verify
export ACME_EMAIL=ops@shop.test
export ADMIN_ALLOWED_CIDRS=192.0.2.10/32
export DJANGO_ALLOWED_HOSTS=shop.example.test,www.shop.example.test
export SITE_ADDRESS=shop.example.test
export SITE_WWW_ADDRESS=www.shop.example.test
export CADDY_HTTP_PORT=8080

docker compose --env-file .env.example config --quiet
docker compose -f compose.prod.yaml config --quiet
docker run --rm --volume "$PWD/infra/caddy/Caddyfile.dev:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker run --rm --env SITE_ADDRESS --env SITE_WWW_ADDRESS --env ACME_EMAIL --volume "$PWD/infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

docker compose -f compose.prod.yaml build
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend
docker compose --env-file .env.example build
docker compose --env-file .env.example up --detach

for path in healthz health; do
  curl --fail --retry 20 --retry-connrefused --retry-delay 1 "http://localhost:${CADDY_HTTP_PORT}/${path}"
done

docker compose --env-file .env.example down --volumes --remove-orphans
export DJANGO_ALLOWED_HOSTS=shop.example.test,www.shop.example.test
export CADDY_HTTP_PORT=8081
export CADDY_HTTPS_PORT=8443
docker compose -f compose.prod.yaml up --detach
static_asset=$(mktemp)
docker compose -f compose.prod.yaml exec --no-TTY caddy \
  wget --quiet --output-document=- http://127.0.0.1:9080/static/rest_framework/docs/css/base.css \
  > "$static_asset"
test -s "$static_asset"
