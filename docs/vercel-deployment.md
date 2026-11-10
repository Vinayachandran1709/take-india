# Vercel deployment

Three Vercel projects are connected to the GitHub repository:

| App | Vercel project | Production URL | API variable |
| --- | --- | --- | --- |
| Public storefront and marketing site | `take-india-storefront` | `https://typein.co` | `NEXT_PUBLIC_API_URL` |
| Dashboard | `take-india-dashboard` | `https://take-india-dashboard.vercel.app` | `VITE_API_URL` |
| Early-access landing | `typein-landing` | `https://project-5772r.vercel.app` | `TYPEIN_API_BASE_URL` |

## Current API connections (10 November 2026)

The landing and storefront production builds point to the dedicated Railway
waitlist service at `https://typein-waitlist-api-production.up.railway.app/api/v1`.
Both were rebuilt and a controlled signup succeeded after the previous Render
service was suspended. The storefront's early-access CTA uses the same
`NEXT_PUBLIC_API_URL` as its booking code, so this production setting supports
waitlist submission but does **not** connect V1 booking routes. Changing either
public variable requires a Vercel rebuild.

The dashboard's `VITE_API_URL` remains an obsolete deleted Railway endpoint.
Do not point production dashboard or storefront at the V1 staging service:
its database is a schema-only Neon test branch. Production V1 cutover awaits
verified live schema/migration approval and a frontend API-routing decision.
See [the Railway cutover record](railway-cutover.md).

## API endpoint selection

The deployment script requires an explicit `-ApiUrl` and has no hosting-provider
default. Supply a working, publicly reachable backend API URL including `/api/v1`.
It sets that URL for production, preview, and development in the selected Vercel
project, so review the endpoint before running the script.

The deployment script predates the dedicated waitlist and V1 service split.
It sets one API URL for the selected project across all environments. Review
its target carefully; it cannot configure separate storefront booking and
waitlist API origins. It was not used for the 10 November cutover.

Deploy both apps from the repository root:

```powershell
$ApiUrl = Read-Host 'Working public backend API URL including /api/v1'
.\scripts\deploy-vercel.ps1 -ApiUrl $ApiUrl
```

Deploy one app:

```powershell
.\scripts\deploy-vercel.ps1 -Target storefront -ApiUrl $ApiUrl
.\scripts\deploy-vercel.ps1 -Target dashboard -ApiUrl $ApiUrl
```

Create preview deployments:

```powershell
.\scripts\deploy-vercel.ps1 -Preview -ApiUrl $ApiUrl
```

The Vercel projects are linked to GitHub, so Vercel can also build from Git once
the repository integration is enabled for the chosen branches.

## Public access and backend CORS

SSO deployment protection is disabled for both Vercel projects so the production
aliases can be opened publicly.

For these frontend domains, the backend's `CORS_ORIGINS` must include:

```text
http://localhost:3000,http://localhost:5173,https://take-india-storefront.vercel.app,https://take-india-dashboard.vercel.app
```

This is a historical CORS example, not the current allowlist. The production
Railway waitlist service allows the exact landing and storefront origins. The
V1 Railway staging service allows only local development origins. Do not add
public production origins to staging merely to make a production frontend work.
