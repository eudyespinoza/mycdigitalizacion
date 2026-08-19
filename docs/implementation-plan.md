# mycdigitalizacion implementation plan

## Global constraints

- Single-store B2C ecommerce for Argentina, physical goods, ARS and Spanish.
- Next.js storefront, Django REST API/admin, PostgreSQL, Redis/Celery and Docker Compose.
- Checkout Pro only; Correo Argentino plus pickup; SID outage routes to manual review.
- TDD for domain and user-visible behavior; provider integrations use injectable adapters and contract tests.
- Preserve the approved Pulso Comercial direction and the supplied logo.

## Task 1: Foundation and product contracts

Create the monorepo scaffold, project documentation, environment contracts, Docker development topology, Django and Next.js test harnesses, and shared architectural conventions.

## Task 2: Backend commerce domain and API

Implement catalog, variants, categories, attributes, promotions, carts, customers, fiscal profiles, addresses, orders, stock reservations and public REST endpoints with Django admin.

## Task 3: External providers and checkout

Implement GeoRef, locality, SID, packing, Correo Argentino, Mercado Pago preferences/webhooks/refunds, scheduled reconciliation and provider failure states.

## Task 4: Storefront and checkout experience

Implement the approved responsive landing, catalog/facets, product detail, cart, registration, address map, shipping selection, checkout and order status flows.

## Task 5: CMS, operations and deployment

Complete landing media control, role-based admin actions, exports, Docker/Caddy production services, backups, health checks and operational documentation.

## Task 6: Verification and visual finish

Run backend/frontend/unit/integration/E2E tests, builds, accessibility checks, responsive screenshots, Impeccable detector/reviewer/documenter and record the final design system.
