# Vercel deployment

Two Vercel projects are connected to the GitHub repository:

| App | Vercel project | Production URL | API variable |
| --- | --- | --- | --- |
| Storefront | `take-india-storefront` | `https://take-india-storefront.vercel.app` | `NEXT_PUBLIC_API_URL` |
| Dashboard | `take-india-dashboard` | `https://take-india-dashboard.vercel.app` | `VITE_API_URL` |

## API endpoint selection

The deployment script requires an explicit `-ApiUrl` and has no hosting-provider
default. Supply a working, publicly reachable backend API URL including `/api/v1`.
It sets that URL for production, preview, and development in the selected Vercel
project, so review the endpoint before running the script.

The existing hosted apps were configured to use the now-deleted Railway backend.
Their remote environment variables and deployments have not been changed. See
[Railway removal status](railway-backend.md) for the retired endpoint, preserved
database, and configuration backup. No replacement backend has been deployed;
clients using the retired URL have no working API until the later migration.

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

This is the previously recorded CORS configuration. Repository cleanup does not
change live backend settings or verify that the hosted backend is online.
