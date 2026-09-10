# Railway backend with existing Neon PostgreSQL

Railway hosts only FastAPI. Neon remains the source of truth. The Railway
environment is named `production`, but its database is the existing Neon
development branch, as explicitly requested. No database data is copied.

## Railway resources

- Project: `take-india` (`4c4826a8-0f8d-4ca3-8414-9f0cec36fed7`)
- Environment: `production` (`a6c41c6a-c254-430f-8a66-e1397afe3c6d`)
- Backend: `e68558d0-72b7-448a-b3e5-3311c39a3a8b`
- Build: `backend/Dockerfile`, Python 3.13, non-root runtime user
- Start: Uvicorn on `0.0.0.0:$PORT`
- Railway health check: `/health`
- Normal pre-deploy command: `alembic current` (read-only)

Variables are stored in Railway, not in the image or repository:

| Variable | Value/source |
| --- | --- |
| DATABASE_URL | Existing Neon pooled development URL from local backend/.env |
| DIRECT_DATABASE_URL | Existing Neon direct development URL from local backend/.env |
| ENVIRONMENT | production |
| ALLOW_TEST_DATABASE_RESET | false |
| TEST_DATABASE_URL | Not configured |
| JWT_SECRET_KEY | Newly generated secret stored directly in Railway |
| JWT_ALGORITHM | HS256 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 60 |
| APP_TIMEZONE | Asia/Kolkata |
| BOOKING_HOLD_MINUTES | 10 |
| CORS_ORIGINS | http://localhost:3000,http://localhost:5173 |

Frontend domains can be added to CORS when those applications are deployed.
This deployment uploads the local backend directory; GitHub autodeploy is not
connected. No commits or pushes were performed.

## Verified deployment

Deployment `b2036da7-0a27-4183-ab93-060b92e0b50f` succeeded on 2026-09-11 IST.
Its read-only pre-deploy verification passed for Neon direct connectivity,
schema `cbdbf24900c6`, reset guards, health/docs/OpenAPI, and all three seeded
storefronts and booking-mode availability calls through the Neon pooled URL.
Railway then started Uvicorn and received HTTP 200 on its runtime health check.
The normal pre-deploy setting was restored to `alembic current` afterward.

Public domain creation is pending explicit user approval after automatic
approval review rejected public internet exposure. No external URL has been
created or externally verified.

## Deploy from PowerShell

```powershell
Set-Location 'C:\Github folder\take-india\backend'
railway.cmd up . --path-as-root --project 4c4826a8-0f8d-4ca3-8414-9f0cec36fed7 --environment a6c41c6a-c254-430f-8a66-e1397afe3c6d --service e68558d0-72b7-448a-b3e5-3311c39a3a8b --detach
```

The upload and Docker ignore files exclude local credentials and the virtual
environment. Deploy settings are stored on the Railway service. Database
migrations are not run automatically against Neon.

`python -m deployment.verify` is an optional, read-only acceptance command for
the seeded Phase 1 dataset. It checks Neon URL shape, reset guards, schema head,
health/docs/OpenAPI through ASGI, and seeded storefront/availability reads.
It assumes the three demo merchants still exist and uses 2030-01-07 for
availability. It is not a general-purpose production readiness check.

## Unused Railway Postgres cleanup

The earlier interrupted deployment continued and initialized a Phase 1 schema
in Railway Postgres. The backend variables have since been replaced with the
existing Neon URLs. The Railway Postgres service was left in place at the
user's request.

After confirming the active backend uses Neon:

1. Open the Take-India project and confirm backend variables point to Neon,
   with no `${{Postgres...}}` references.
2. Select only `Postgres` (`23340ee8-0a73-486a-aea8-780c71d0dcad`) and use the
   service deletion action. Do not delete the project or backend service.
3. Review any retained volume named `postgres-volume`
   (`21d5b058-a8fb-451a-aabd-6c659349faff`). If no data in this newly created
   Railway database is needed, delete that volume separately. Volume deletion
   permanently removes its data; export anything needed first.
4. Recheck backend health and an existing Neon storefront.

Leaving the unused database running can continue to incur Railway charges.
Deleting it does not delete the external Neon database.
