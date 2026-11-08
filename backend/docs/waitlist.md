# typein early-access waitlist

The static landing page submits `POST /api/v1/waitlist` to the existing FastAPI
backend. The endpoint accepts JSON with `name`, `business_type`, and `whatsapp`,
matching the two landing forms. No email is collected. The name is required in
both the form and API; the database column is nullable only to preserve entries
created before names were collected. The business type
must be one of the displayed options; an Indian mobile number with optional `+91`
is normalized to E.164. The server limits this route to 4 KiB of JSON.

A new registration and a duplicate number both return HTTP 200 with
`{"accepted":true}`. The database uniqueness constraint prevents duplicate rows.
A retry can fill in a missing name on an older entry; it cannot overwrite an
existing name or business type.
Invalid input returns HTTP 400 with field guidance. A body over 4 KiB returns 413;
an unavailable database returns 503 with a generic message. The response does not
echo a phone number or database details. No booking, payment or message is created.
The route limits each client to 60 requests per 10 minutes in one process. On Render,
it uses the edge-provided client address; locally it uses the socket address. This
basic in-memory limit resets on restart and is not shared across instances. Use a
distributed limit if the service is scaled beyond one instance. CORS alone does not
prevent abuse.

`app.waitlist_main:app` is the dedicated public entry point. It exposes only
`/health` and `/api/v1/waitlist`; booking, payment, and merchant routes remain out
of this waitlist service. The full product entry point remains `app.main:app`.

The new `waitlist_entries` model uses the existing SQLAlchemy base and async
session. Migration `f93a4c1236de` follows source revision `e82f3b0125cd` and only
adds the table, UUID primary key, unique normalized WhatsApp number, business type,
creation timestamp, and consent timestamp. Downgrade removes only this table.
The next additive migration `a7d8c9012f34` adds a nullable name column (up to 120
characters) so existing entries remain valid. Its downgrade removes only that column.
It was applied to the isolated `typein-waitlist` branch on November 2, 2026;
the applied revision and six waitlist columns were verified. Two existing entries
were preserved and have no name because they predate the new form.
On November 2, 2026, the approved isolated Neon branch `typein-waitlist` was forked
from `development`. It started at `cbdbf24900c6`; the offline Alembic-generated SQL
for `d71e2a9014bc`, `e82f3b0125cd`, and `f93a4c1236de` was applied to that branch
in transactions through the Neon SQL Editor. The final revision and five waitlist
columns were verified, with zero rows. The original development branch remained at
`cbdbf24900c6`. The production branch had no `alembic_version` table and was not
migrated. Never assume either original branch is at the new head.

## Local development

Use a database specifically approved for development. Never point these commands
at production or staging by accident. From `backend/`, install its existing pinned
requirements into its own virtual environment if they are not already installed.
Set `DATABASE_URL` for the local development backend through its normal private
configuration. Preserve existing `CORS_ORIGINS` and append
`http://127.0.0.1:4173`. Then run:

```cmd
cd /d "C:\Github folder\take-india\backend"
.\.venv\Scripts\python.exe -m uvicorn app.waitlist_main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from `landing/`:

```cmd
cd /d "C:\Github folder\take-india\landing"
set "TYPEIN_API_BASE_URL=http://127.0.0.1:8000/api/v1"
node server.mjs
```

Open `http://127.0.0.1:4173`. The backend's `/health` endpoint checks process
availability only; it does not prove database availability or migration state.
The form cannot save until the new table is applied to the selected development
database. An unset frontend API URL leaves both forms visibly unavailable.

## Isolated checks

`backend/tests/` uses an autouse fixture that truncates a configured PostgreSQL
test database, so it is deliberately excluded from this feature's safe local check.
The waitlist runner empties database URL settings in its own process before importing
the app, runs focused HTTP tests with a private in-memory table, checks the offline
migration shape, and runs database-free payment security regressions:

```cmd
cd /d "C:\Github folder\take-india\backend"
.\.venv\Scripts\python.exe -m scripts.check_waitlist
.\.venv\Scripts\python.exe -m ruff check app\api\v1\waitlist.py app\api\router.py app\core\waitlist_rate_limit.py app\waitlist_main.py app\models\waitlist.py app\models\__init__.py app\schemas\waitlist.py unit_tests\test_waitlist.py scripts\check_waitlist.py
```

One unrelated existing payment regression requires a Pytest temporary directory
that is inaccessible in this Windows sandbox, so the runner deselects just that
case. No real database is reset or contacted.

## Before public collection

1. Review the short WhatsApp contact line and linked privacy page in `landing/`.
2. Select a backend host and configure private `DATABASE_URL` and, for migrations,
   `DIRECT_DATABASE_URL` using the existing backend conventions.
3. Use only the isolated `typein-waitlist` branch for this service. Its revision
   was verified at `a7d8c9012f34`; verify branch identity before setting credentials.
4. Set `CORS_ORIGINS` for the dedicated waitlist service to the exact landing origin.
   The process-local abuse limit is enabled; keep this service to one instance unless
   a shared limit is added.
5. Give the landing build the **public**, HTTPS `TYPEIN_API_BASE_URL` ending in
   `/api/v1`. In Vercel this is a build-time setting for the separate landing
   project with Root Directory `landing`, Build Command `node scripts/build.mjs`,
   and Output Directory `dist`. Rebuild after changing the URL.
6. Submit a test registration and verify the record in the `typein-waitlist` Neon
   branch before opening sign-ups to the public.

Required configuration names: `DATABASE_URL`, `DIRECT_DATABASE_URL` (migration
only), `CORS_ORIGINS`, `TYPEIN_API_BASE_URL`. Values and credentials do not belong
in the repository or public frontend files.
