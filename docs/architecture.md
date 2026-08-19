# Architecture contracts

## Runtime boundaries

The storefront (`frontend/`) is a Next.js 16.3 App Router application using React 19, TypeScript and Tailwind CSS 4.3. The API and back office (`backend/`) use Django 5.2 LTS and Django REST Framework. PostgreSQL is the system of record; Redis is the Celery broker/result backend. Caddy is the only public entry point in containers. Development Caddy listens explicitly on HTTP localhost; production Caddy is HTTPS-enabled and requires a public `SITE_ADDRESS`.

`GET /healthz` is an unauthenticated, non-sensitive liveness endpoint for the Django process. `GET /health` is the corresponding storefront availability page. Future readiness checks may include dependency checks, but they must not leak credentials, provider responses or customer data.

## Product and data boundaries

- API endpoints are namespaced below `/api/` when introduced; Caddy forwards that path to Django.
- Each provider (SID RENAPER, GeoRef, locality data, Correo Argentino and Mercado Pago) is isolated behind an adapter interface. Applications consume contracts, not provider SDKs.
- Provider and payment webhooks must validate authenticity, preserve idempotency and remain auditable.
- Sensitive identity, address and fiscal fields are never emitted to application logs. Exports require explicit staff authorization and an audit event.
- All prices, stock, shipping and identity eligibility are authoritative only after server-side recalculation. Stock reservations expire after 20 minutes.

## Delivery operations

Development uses `compose.yaml` with bind mounts; `compose.prod.yaml` removes source mounts and runs the production targets. The production Caddy instance owns HTTP/TLS entry and reverse-proxies application traffic. Django runs `collectstatic` before the production web process starts; its `static_files` volume is mounted read-only into Caddy and served at `/static/*`. Database, static and Caddy volumes are persistent and must be backed up by the deployment operator.

No example configuration carries a live API key or provider secret. The `.env.example` values are deliberately non-production placeholders. Production startup requires `APP_ENV=production` and rejects missing or known placeholder signing keys, database passwords and site configuration.
