# Railway backend history

**Current status (10 November 2026):** The dedicated waitlist API runs on
Railway production at `https://typein-waitlist-api-production.up.railway.app`.
The V1 API runs separately on Railway staging at
`https://typein-v1-api-staging.up.railway.app`. The replaced Render waitlist
service is suspended. See [the current cutover record](railway-cutover.md)
for service configuration, validation, rollback, and the remaining production
V1 blocker. The rest of this document records the earlier Railway removal;
its statements about current availability are historical.

## Historical removal (13 October 2026)

Railway deployment support has been removed from the repository. On 2026-10-13
(India time), the backend service and its domain were deleted after preserving
its environment settings. The local backend directory's Railway CLI link was
also removed. No replacement hosting has been configured.

The user explicitly required that no database be deleted or changed. The
Railway Postgres service, its volume, and their containing project/environment
are therefore retained. Neon was not accessed or changed. Railway removal is
not complete while this database storage remains; charges are not confirmed
stopped.

## Repository cleanup

- Removed `backend/.railwayignore` and the Railway upload instructions.
- Removed the hardcoded Railway API default from `scripts/deploy-vercel.ps1`.
  Future Vercel deployments require an explicit working `-ApiUrl`.
- Preserved `backend/Dockerfile`, `.dockerignore`, and `deployment/verify.py`:
  they support a generic Python/Uvicorn container and a Neon-specific read-only
  Phase 1 check without requiring Railway.
- No Railway SDK, repository CI/CD workflow, `railway.json`, `railway.toml`,
  Railpack/Nixpacks configuration file, or application-code dependency was found.
- Local backend environment files use external Neon endpoints; frontend local
  environment files use localhost. No Railway references were found in those
  files, and their values were left unchanged.

## Remaining account resources

Post-deletion Railway inspection on 2026-10-13 (India time) confirmed one
environment, one remaining service (Postgres), one volume, no buckets, and no
staged changes. Postgres remains **offline**, with its original volume attached.
The backend is absent. An offline status is not confirmation of zero charges.

| Resource | Name / ID | Observed configuration |
| --- | --- | --- |
| Project | `take-india` / `4c4826a8-0f8d-4ca3-8414-9f0cec36fed7` | Retained to preserve the database |
| Environment | `production` / `a6c41c6a-c254-430f-8a66-e1397afe3c6d` | Retained to preserve the database |
| Backend service | `backend` / `e68558d0-72b7-448a-b3e5-3311c39a3a8b` | Deleted; had no attached volumes |
| Database service | `Postgres` / `23340ee8-0a73-486a-aea8-780c71d0dcad` | Preserved unchanged; offline; PostgreSQL 18 image; no public domain or TCP proxy |
| Persistent volume | `postgres-volume` / `21d5b058-a8fb-451a-aabd-6c659349faff` | 5000 MB provisioned in `us-west2`; mounted on Postgres at `/var/lib/postgresql/data` |
| Backend domain | `backend-production-b809.up.railway.app` / `13d68e4c-39d6-434b-8153-324ac0b8a24d` | Removed with the backend service |

## Preserved backend settings

Before deletion, all 21 rendered backend variables were saved to the Git-ignored
file `backend/.env.railway-backend-backup.clixml`. It contains an encrypted
SecureString holding the variables as JSON, including the JWT secret, database
connection settings, CORS settings, and the old injected Railway variables.
The backup was imported, decrypted, and compared with the original in memory
before deletion; no secret values were printed or added to Git. This is a
configuration backup, not a database backup.

PowerShell's Windows encryption binds this backup to the Windows account and
computer that created it. Keep it available for future configuration recovery;
`Import-Clixml` under that account returns the SecureString. Do not overwrite
local `.env` files with it or reuse obsolete Railway-injected variables for a
future host. Existing local environment files were verified unchanged.

The retired service used `Dockerfile`, health check `/health` with a 120-second
timeout, three restart retries, one `us-west2` replica, and the read-only
pre-deploy command `alembic current`. Its domain routed to container port 8080.
There was no GitHub source connection, attached volume, or staged change.

## Known dependencies and shutdown impact

Before deletion, the backend's `DATABASE_URL` and `DIRECT_DATABASE_URL` were
confirmed to reference external Neon hosts by inspecting configuration only.
No connection to Neon or any other database was opened. The earlier deployment
record identifies this as the original Neon development branch despite the
environment name `production`.

That record says Railway Postgres was left behind after an earlier deployment
initialized a Phase 1 schema there. Its database and volume remain intact;
their contents were not read, exported, reset, or changed. All external Neon
databases must also remain intact.

The Vercel storefront and dashboard were previously configured with:

```text
https://backend-production-b809.up.railway.app/api/v1
```

Their respective variables are `NEXT_PUBLIC_API_URL` and `VITE_API_URL`. Remote
Vercel settings were not changed or re-verified. The endpoint above is now
retired: clients still using it have no working backend. The service was already
reported offline before removal. There is no replacement endpoint. Local
development continues using localhost and Neon.

## Remaining work outside this removal

1. Preserve the Railway Postgres service, its volume, and the containing
   project/environment. Their deletion is not authorized. Fully leaving Railway
   while retaining that database requires a separately authorized data
   preservation/migration plan. No database export or recovery was attempted.
2. During the later hosting migration, configure the new API URL in the Vercel
   projects and any external consumers or callbacks before rebuilding clients.
   No Vercel deployments, Google setup, or Razorpay settings were changed here.
3. Retained storage may continue to incur Railway charges. Review usage/billing
   without deleting the protected database or volume. Other Railway projects
   and the shared CLI installation remain outside this project's cleanup.

## Historical verification retained

Deployment `b2036da7-0a27-4183-ab93-060b92e0b50f` succeeded on 2026-09-11 IST.
The prior record reports successful Neon connectivity, Phase 1 schema
`cbdbf24900c6`, reset guards, and seeded storefront/availability reads.
Public HTTPS was subsequently enabled with explicit user approval; external
checks passed for `/health`, `/docs`, `/openapi.json`, and all three seeded
storefronts and their availability endpoints, without creating bookings.
Deployment `d7130d3f-8bc4-4d38-aa48-9e656409c784` later applied the Vercel CORS
origins. These are historical results, not current availability guarantees.

The preserved `deployment.verify` helper assumes the original Phase 1 revision,
three demo merchants, and availability on 2030-01-07. It is not a general-purpose
production readiness check or a Phase 2 schema check.
