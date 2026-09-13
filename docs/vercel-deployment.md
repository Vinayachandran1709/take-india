# Vercel deployment

Two Vercel projects are connected to the GitHub repository:

| App | Vercel project | Production URL | API variable |
| --- | --- | --- | --- |
| Storefront | `take-india-storefront` | `https://take-india-storefront.vercel.app` | `NEXT_PUBLIC_API_URL` |
| Dashboard | `take-india-dashboard` | `https://take-india-dashboard.vercel.app` | `VITE_API_URL` |

Both point to the Railway backend API:

```text
https://backend-production-b809.up.railway.app/api/v1
```

Deploy both apps from the repository root:

```powershell
.\scripts\deploy-vercel.ps1
```

Deploy one app:

```powershell
.\scripts\deploy-vercel.ps1 -Target storefront
.\scripts\deploy-vercel.ps1 -Target dashboard
```

Create preview deployments:

```powershell
.\scripts\deploy-vercel.ps1 -Preview
```

The Vercel projects are linked to GitHub, so Vercel can also build from Git once
the repository integration is enabled for the chosen branches.

## Backend CORS

The Railway backend currently allows localhost origins only. The Vercel domains
need to be added to `CORS_ORIGINS` before browser API calls from production can
work:

```text
http://localhost:3000,http://localhost:5173,https://take-india-storefront.vercel.app,https://take-india-dashboard.vercel.app
```

This changes the existing Railway backend service configuration and causes a
backend redeploy. It does not touch Neon or the unused Railway PostgreSQL service.
