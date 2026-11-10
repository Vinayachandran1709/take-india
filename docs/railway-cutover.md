# Backend cutover: Render to Railway

Status checked on 10 November 2026. This document records observed deployments;
it contains no credentials. The backend and frontends use separate projects and
database branches. Do not replace a production database URL with a staging URL.

## Services and data

| Environment | Service | Entry point | Public origin | Neon branch |
| --- | --- | --- | --- | --- |
| Railway production | `typein-waitlist-api` | `app.waitlist_main:app` | `https://typein-waitlist-api-production.up.railway.app` | `typein-waitlist` |
| Railway staging | `typein-v1-api` | `app.v1_main:app` | `https://typein-v1-api-staging.up.railway.app` | `typein-v1-staging` |

Both services build from `backend/` with its Dockerfile, bind to Railway's
`PORT`, and use `/health` as their process health check. Neither runs a
migration at startup. The retained Railway Postgres service and volume were
not repurposed, migrated, or deleted. Neon remains the database provider.

The waitlist Neon branch was verified at Alembic revision `a7d8c9012f34`.
The V1 staging Neon branch was created schema-only from development, verified
empty, stamped at the copied schema revision `cbdbf24900c6`, and migrated to
`b7e3f29c41aa` on that isolated branch only. The live production Neon branch
has no Alembic version table; its applied schema remains unverified. No live
production migration was run.

## Public connections and checks

The Vercel `typein-landing` production build uses `TYPEIN_API_BASE_URL` and
the `take-india-storefront` production build uses `NEXT_PUBLIC_API_URL`, both
pointing to the Railway waitlist origin plus `/api/v1`. Controlled signups,
including one after Render suspension, returned HTTP 200. Landing, storefront,
Railway health, and landing public config returned HTTP 200. The Railway
waitlist CORS preflight allowed the exact landing origin; a public storefront
origin was also allowed in the post-suspension submission test. The waitlist
service uses one instance because its rate limiter is process-local. The
Railway-specific client-address path uses the edge-provided `X-Real-IP` header;
its live per-visitor behavior has not been tested with multiple remote clients.

The Railway V1 staging service returned HTTP 200 for health and OpenAPI,
connected to its intended Neon branch at `b7e3f29c41aa`, and returned the
expected not-found response after a database-backed storefront lookup. A
synthetic staging merchant signup returned 201; login, account summary,
billing summary, and public merchant page returned 200. Its CORS preflight
allowed localhost development and rejected `https://typein.co`. No real
payments, customer messages, or provider-delivered webhooks were exercised.
Database-free backend unit tests passed (107 tests).

## Configuration names

Production waitlist: `ASGI_APP`, `ENVIRONMENT`, `DATABASE_URL`,
`CORS_ORIGINS`. Direct database access is needed only for an explicitly
approved migration or audit, not ordinary requests.

V1 staging: `ASGI_APP`, `ENVIRONMENT`, `DATABASE_URL`,
`DIRECT_DATABASE_URL`, `JWT_SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`,
`JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`,
`PUBLIC_API_URL`, `APP_TIMEZONE`, `BOOKING_HOLD_MINUTES`,
`BILLING_TRIAL_DAYS`, `BILLING_PLAN_AMOUNT_PAISE`, `BILLING_TOTAL_COUNT`.
The staging instance does not have WhatsApp, Resend, or Razorpay credentials.
`ALLOW_TEST_DATABASE_RESET` is not enabled on either deployed service.

## Remaining production V1 boundary

The V1 service is only staging. The dashboard production build still has
`VITE_API_URL` pointing to the previously deleted Railway backend domain.
The storefront production API variable currently points to the waitlist-only
service; its booking code and early-access CTA share one variable. Do not
switch these production variables to V1 staging. The production V1 launch
requires a verified target Neon schema and approved migration plan, production
credentials, the correct public CORS origins, and a frontend configuration
that can address booking and waitlist APIs separately. A test Razorpay plan,
keys, and webhook secret must remain isolated from production billing.

The merchant subscription webhook route is `/api/v1/webhooks/razorpay` on
the V1 API, separate from the older booking-payment webhook. No subscription
webhook was created or redirected during this host migration. No Meta or
email callback was changed. A stable `api.typein.co` domain was not assigned;
the Railway-generated HTTPS origins above are currently used.

## Render retirement and rollback

The only Render backend service found was `typein-waitlist-api`. It had no
attached disk; data is in Neon. After both public sites were rebuilt and
verified against Railway, the Render service was **suspended**, not deleted.
Render reports suspended services are not billed. Keep it available until
external callback inventory and a longer observation period are complete.
No Render database, disk, unrelated service, or account was removed.

To roll back the waitlist host, resume `typein-waitlist-api` in Render, change
`TYPEIN_API_BASE_URL` for the landing and `NEXT_PUBLIC_API_URL` for the
storefront to its previous public origin plus `/api/v1`, rebuild both Vercel
projects, and verify a controlled submission. That fallback uses the same
Neon waitlist branch. V1 staging has no production traffic to roll back.
