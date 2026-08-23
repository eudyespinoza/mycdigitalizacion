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
export DJANGO_SECRET_KEY=ci-signing-key-not-for-production-and-long-enough
export DJANGO_ALLOWED_HOSTS=shop.example.test
export SITE_ADDRESS=shop.example.test
export SITE_WWW_ADDRESS=www.shop.example.test
export CADDY_HTTP_PORT=8080

docker compose --env-file .env.example config --quiet
docker compose -f compose.prod.yaml config --quiet
docker run --rm --volume "$PWD/infra/caddy/Caddyfile.dev:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker run --rm --env SITE_ADDRESS --env SITE_WWW_ADDRESS --volume "$PWD/infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

docker compose --env-file .env.example build
docker compose -f compose.prod.yaml build
docker compose --env-file .env.example up --detach

for path in healthz health; do
  curl --fail --retry 20 --retry-connrefused --retry-delay 1 "http://localhost:${CADDY_HTTP_PORT}/${path}"
done

docker compose --env-file .env.example down --volumes --remove-orphans
export SITE_ADDRESS=http://shop.example.test
export SITE_WWW_ADDRESS=http://www.shop.example.test
export CADDY_HTTP_PORT=8081
export CADDY_HTTPS_PORT=8443
docker compose -f compose.prod.yaml up --detach
static_asset=$(mktemp)
curl --fail --retry 20 --retry-connrefused --retry-delay 1 \
  --resolve "shop.example.test:${CADDY_HTTP_PORT}:127.0.0.1" \
  "http://shop.example.test:${CADDY_HTTP_PORT}/static/admin/css/base.css" \
  --output "$static_asset"
test -s "$static_asset"
