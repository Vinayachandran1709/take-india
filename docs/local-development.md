# Local development on Windows

## Requirements

- Git 2.51 or newer
- Python 3.13
- Node.js 24 and npm 11
- A Neon project with a `development` branch and an isolated `test` child branch

Run all commands from the child repository. Do not run Git commands from its parent repository.

```powershell
Set-Location 'C:\Github folder\take-india'
```

## Backend setup

```powershell
Set-Location 'C:\Github folder\take-india\backend'
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit the untracked `backend/.env` directly. Do not paste secrets into chat or commit them.

- `DATABASE_URL`: development branch pooled Neon URL, used by FastAPI.
- `DIRECT_DATABASE_URL`: development branch direct Neon URL, used by Alembic.
- `TEST_DATABASE_URL`: isolated test branch direct Neon URL, used only by tests.
- `JWT_SECRET_KEY`: a strong local value of at least 32 characters.
- `ALLOW_TEST_DATABASE_RESET=true`: explicit permission for the isolated test branch only.

PostgreSQL URLs are normalized centrally to `postgresql+asyncpg://`; required Neon TLS parameters are preserved. Verify all connections without printing URLs:

```powershell
python -m scripts.check_db
alembic upgrade head
alembic current
alembic history
python -m scripts.seed
python -m uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`; health and interactive documentation are at `/health` and `/docs`.

Seed execution is refused unless `ENVIRONMENT=development`. It is idempotent and creates:

| Login | Storefront | Mode |
|---|---|---|
| `glow@example.com` | `glow-salon-spa` | Appointment |
| `beatz@example.com` | `beatz-dance-studio` | Batch |
| `crumbs@example.com` | `sweet-crumbs` | Custom order |

All three use the local-only password `TakeIndiaLocal123!`.

## Frontend setup

In separate PowerShell windows:

```powershell
Set-Location 'C:\Github folder\take-india\storefront'
Copy-Item .env.example .env.local
npm ci
npm run dev
```

```powershell
Set-Location 'C:\Github folder\take-india\dashboard'
Copy-Item .env.example .env.local
npm ci
npm run dev
```

The storefront uses port 3000 and the dashboard uses port 5173. Default CORS origins use `localhost`; keep the same hostname in the browser.

## Test safety

Tests never fall back to `DATABASE_URL`. Before any `TRUNCATE`, the test harness requires every condition below:

```text
ENVIRONMENT=test
TEST_DATABASE_URL is configured
TEST_DATABASE_URL != DATABASE_URL
ALLOW_TEST_DATABASE_RESET=true
```

Run migrations and tests on the isolated branch:

```powershell
$env:ENVIRONMENT = 'test'
alembic upgrade head
pytest
Remove-Item Env:ENVIRONMENT
```

If any guard is absent, destructive setup exits with `Unsafe test database configuration` and lists the failed conditions.

## Verification commands

```powershell
Set-Location 'C:\Github folder\take-india\backend'
ruff check .
pytest

Set-Location 'C:\Github folder\take-india\storefront'
npm run lint
npm run build

Set-Location 'C:\Github folder\take-india\dashboard'
npm run lint
npm run build
```
