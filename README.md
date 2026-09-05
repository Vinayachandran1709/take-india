# Take-India

Take-India Phase 1 is a multi-tenant booking foundation for Indian local businesses. It supports staff appointments, capacity-limited batches, and lead-time-validated custom orders through a FastAPI API, public Next.js storefront, and React/Vite merchant dashboard.

Public initiation creates an unpaid temporary hold only. Payments, WhatsApp automation, notifications, reviews, retention, deployment, POS, inventory, CRM, and analytics are intentionally outside Phase 1.

## Repository layout

- `backend/` — FastAPI, SQLAlchemy async, Alembic, seed, and PostgreSQL tests.
- `storefront/` — public Next.js App Router experience.
- `dashboard/` — merchant React/Vite configuration workspace.
- `docs/` — setup, API, booking semantics, and future Meta preparation.

## Start here

Follow [Local development](docs/local-development.md), then see the [API contract](docs/api.md) and [booking engine rules](docs/booking-engine.md).

Demo storefronts after seeding:

- `http://localhost:3000/glow-salon-spa`
- `http://localhost:3000/beatz-dance-studio`
- `http://localhost:3000/sweet-crumbs`

The development-only demo accounts use the password `TakeIndiaLocal123!` with the emails documented in the local setup guide.
