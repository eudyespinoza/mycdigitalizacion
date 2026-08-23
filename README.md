# mycdigitalizacion

Monorepo for the Argentine B2C physical-goods storefront and operations API. The public experience follows the approved **Pulso Comercial** direction: navy structure, cyan wayfinding and magenta conversion, while preserving the supplied rounded logo and approved reference composition.

## Repository layout

- `frontend/` — Next.js App Router storefront (React, TypeScript, Tailwind CSS).
- `backend/` — Django REST API, Django administration and Celery configuration.
- `infra/` — edge-proxy configuration.
- `docs/` — durable product and architecture decisions.

## Local development

1. Copy `.env.example` to `.env` and keep `APP_ENV=development` for local Docker work.
2. Start the full topology: `docker compose up --build`.
3. In another terminal, prepare the local database: `docker compose exec backend python manage.py migrate`.
4. Open `http://localhost`; API process health is available at `http://localhost/healthz`, and storefront health at `http://localhost/health`.

The Docker topology includes Next.js, Django, a Celery worker, PostgreSQL, Redis and Caddy. Development Caddy is deliberately HTTP-only at `http://localhost`; production Caddy is HTTPS-enabled and requires a canonical `SITE_ADDRESS` plus a `SITE_WWW_ADDRESS` that redirects to it. Set `CADDY_HTTP_PORT` if port 80 is occupied. The browser API base is same-origin `/api`.

For production-like containers, set `APP_ENV=production`, a non-placeholder Django secret/database password, a public `SITE_ADDRESS`, and matching `DJANGO_ALLOWED_HOSTS`; then use `docker compose -f compose.prod.yaml run --rm backend python manage.py migrate`, followed by `docker compose -f compose.prod.yaml up --build -d`. Production startup rejects missing or known development placeholders.

## Local quality checks

```powershell
corepack pnpm install
corepack pnpm lint
corepack pnpm test:ci
corepack pnpm build

python -m venv .venv
$env:APP_ENV = "test"
.\.venv\Scripts\python -m pip install --require-hashes -r backend\requirements-dev.lock
.\.venv\Scripts\python -m ruff check backend
.\.venv\Scripts\python -m pytest backend
```

On Linux/macOS, `bash scripts/verify-containers.sh` validates both Compose topologies and Caddyfiles, builds their images, and smoke-tests `/healthz` and `/health` through development Caddy. CI runs this same contract.

## Architecture conventions

- Monetary, inventory, shipping and identity decisions are recalculated by the server at irreversible boundaries.
- Provider integrations belong behind injectable adapters; no live provider credential is required for development or tests.
- Personal and fiscal data must be masked from logs and have auditable access paths.
- Future sellable items are variants with unique SKUs; category depth is capped at five levels.
- Tests are Vitest/Testing Library in `frontend/tests` and pytest/pytest-django in `backend/tests`.

See [PRODUCT.md](PRODUCT.md) and [docs/architecture.md](docs/architecture.md) for the product and system contracts.
