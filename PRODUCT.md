# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js 16 App Router with React, TypeScript and Tailwind CSS 4 for the storefront; Django 5.2 LTS and Django REST Framework for the API and administration; PostgreSQL, Redis and Celery; Docker Compose on a dedicated Donweb VPS.

## Users

- Argentine consumers buying physical products from a multi-category catalog.
- Store staff managing catalog, inventory, promotions, customers, orders, landing content, billing exports and shipping.
- Store owners administering credentials, permissions and business settings.

## Product Purpose

mycdigitalizacion is a single-store B2C ecommerce experience. It lets a customer discover products, register and verify their identity, locate an address, obtain a real shipping quote, pay with Mercado Pago and track the resulting order. Success means that the commercial flow can be operated end to end without editing code.

## Positioning

The store joins a visually rich multi-category catalog with identity-aware checkout, precise map confirmation and carrier-backed packing, pricing, labels and tracking in one operating flow.

## Operating Context

- Spanish (Argentina), Argentine pesos and physical inventory by SKU.
- National delivery through Correo Argentino and configurable free pickup.
- Payment through Mercado Pago Checkout Pro.
- Customer and fiscal data may contain sensitive personal information and must remain masked, auditable and absent from application logs.
- Production runs in containers on a dedicated VPS.

## Capabilities and Constraints

- Landing, catalog, dynamic facets, cart, customer account, fiscal profile, identity review, address map, shipping quotes, checkout, orders and post-sale administration.
- Product category trees allow up to five levels; every sellable unit is a variant with a unique SKU.
- Each variant can use finite stock or infinite stock. Finite stock is reserved for 20 minutes while the customer pays and is consumed only after payment approval; infinite stock is never decremented or restored.
- Each variant can define an optional maximum quantity per cart. A blank maximum means no commercial limit; finite variants remain bounded by their available stock and all variants retain a high technical safety ceiling.
- SID RENAPER, GeoRef, Andreani locality data, Correo Argentino and Mercado Pago are isolated behind provider adapters.
- If SID is unavailable, checkout enters manual identity review without payment or stock reservation.
- V1 stores and exports fiscal data but does not issue ARCA electronic invoices.
- V1 excludes marketplaces, multiple stores, digital goods, reviews, wishlists, local courier delivery and active non-Correo carriers. Social profiles and a floating WhatsApp contact are optional landing settings and remain hidden until configured.

## Brand Commitments

- Public name: mycdigitalizacion.
- Preserve the supplied rounded logo and its navy, cyan and magenta identity.
- Chosen public visual direction: Pulso Comercial — luminous, trustworthy, energetic and conversion-oriented.
- Copy is direct, friendly and useful; it avoids fabricated claims and invented social proof.

## Evidence on Hand

- Supplied PNG logo from the project owner.
- Approved Pulso Comercial desktop concept generated during planning.
- Existing `kepedimos` Mercado Pago implementation at `D:\\devlink\\TuPedido` as a security and idempotency reference.
- No real product catalog, prices, testimonials or commercial metrics were supplied; development data must be explicitly synthetic.

## Product Principles

1. Recalculate price, stock, identity and shipping on the server at every irreversible boundary.
2. Make external-provider failure visible and recoverable; never fabricate approval, location or cost.
3. Keep commerce fast and legible while preserving the brand's distinctive energy.
4. Give non-technical staff complete control over catalog and landing content within safe layout constraints.
5. Treat accessibility, privacy, auditability and operational recovery as product features.

## Accessibility & Inclusion

Target WCAG 2.2 AA, complete keyboard operation, visible focus, reduced-motion support, sufficient contrast and a non-map textual path for address confirmation.
