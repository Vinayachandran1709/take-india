"""HTTP + real in-memory persistence checks. No configured PostgreSQL is contacted."""

import importlib.util
from io import StringIO
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.waitlist import waitlist_database
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.waitlist_rate_limit import WaitlistRateLimiter
from app.main import app
from app.models.waitlist import WaitlistEntry
from app.waitlist_main import app as public_waitlist_app

VALID = {"name": "Asha", "business_type": "Salon & hair studio", "whatsapp": "9876543210"}
ORIGIN = "http://127.0.0.1:4173"


class IsolatedSession:
    """An async-shaped adapter over a real, private SQLite session, for HTTP tests."""

    def __init__(self, session):
        self.session = session
        self.statements = []
        self.fail_at = None
        self.rollbacks = 0

    async def execute(self, statement):
        self.statements.append(statement)
        if self.fail_at == "execute":
            raise SQLAlchemyError("internal database detail that must not be returned")
        if self.fail_at == "connect":
            raise OSError("internal database detail that must not be returned")
        return self.session.execute(statement)

    async def commit(self):
        if self.fail_at == "commit":
            raise SQLAlchemyError("internal database detail that must not be returned")
        self.session.commit()

    async def rollback(self):
        self.rollbacks += 1
        self.session.rollback()


@pytest.fixture
def isolated_db():
    assert not get_settings().database_url, "Run with python -m scripts.check_waitlist"
    engine = create_engine("sqlite+pysqlite:///:memory:")
    # Only the new table is created, entirely in memory. Existing metadata is not created/reset.
    WaitlistEntry.__table__.create(engine)
    with Session(engine) as session:
        yield IsolatedSession(session)
    engine.dispose()


@pytest_asyncio.fixture
async def client(isolated_db):
    async def override():
        yield isolated_db

    app.dependency_overrides[waitlist_database] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.pop(waitlist_database, None)


async def test_registration_inserts_only_waitlist_and_normalizes(client, isolated_db):
    response = await client.post(
        "/api/v1/waitlist",
        json={
            "name": " Asha ",
            "business_type": " Salon & hair studio ",
            "whatsapp": " +91 98765-43210 ",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": True}
    assert response.headers["cache-control"] == "no-store"
    entry = isolated_db.session.scalar(select(WaitlistEntry))
    assert entry.whatsapp == "+919876543210"
    assert entry.name == "Asha"
    assert entry.business_type == VALID["business_type"]
    assert entry.id and entry.created_at
    assert entry.consented_at
    assert len(isolated_db.statements) == 1
    statement = isolated_db.statements[0]
    assert statement.table.name == "waitlist_entries"
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "ON CONFLICT (whatsapp) DO NOTHING" in str(compiled)
    assert entry.whatsapp not in str(compiled)  # Bound parameters, never interpolated SQL.


async def test_duplicate_formats_leave_one_original_entry(client, isolated_db):
    first = await client.post("/api/v1/waitlist", json=VALID)
    repeated = await client.post(
        "/api/v1/waitlist",
        json={"name": "Other name", "business_type": "Other", "whatsapp": "+91 98765 43210"},
    )
    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json() == {"accepted": True}
    assert isolated_db.session.scalar(select(func.count()).select_from(WaitlistEntry)) == 1
    assert isolated_db.session.scalar(select(WaitlistEntry.business_type)) == VALID["business_type"]
    assert isolated_db.session.scalar(select(WaitlistEntry.name)) == VALID["name"]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"business_type": "Other"},
        {"whatsapp": VALID["whatsapp"]},
        {**VALID, "name": ""},
        {**VALID, "name": " "},
        {**VALID, "name": "x" * 121},
        {**VALID, "name": 123},
        {**VALID, "consent": True},
        {**VALID, "whatsapp": "bad-phone"},
        {**VALID, "whatsapp": "1234567890"},
        {**VALID, "whatsapp": "+14155552671"},
        {**VALID, "whatsapp": "9" * 100},
        {**VALID, "whatsapp": 9876543210},
        {**VALID, "whatsapp": None},
        {**VALID, "business_type": "not listed"},
        {**VALID, "business_type": "x" * 1000},
        {**VALID, "email": "not-collected@example.invalid"},
        [VALID],
    ],
)
async def test_invalid_payloads_never_insert(client, isolated_db, payload):
    response = await client.post("/api/v1/waitlist", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "input" not in response.text
    assert "bad-phone" not in response.text
    assert "not-collected@" not in response.text
    assert isolated_db.statements == []


@pytest.mark.parametrize(
    "business_type",
    [
        "Salon & hair studio",
        "Makeup, lash & nail artist",
        "Custom baker",
        "Aesthetic or dental clinic",
        "Yoga, dance or fitness studio",
        "Other",
    ],
)
async def test_all_displayed_business_types_and_no_extra_personal_fields(client, business_type):
    result = await client.post("/api/v1/waitlist", json={**VALID, "business_type": business_type})
    assert result.status_code == 200


async def test_old_form_payload_can_submit_during_rollout(client, isolated_db):
    result = await client.post(
        "/api/v1/waitlist",
        json={"business_type": VALID["business_type"], "whatsapp": VALID["whatsapp"]},
    )
    assert result.status_code == 200
    assert isolated_db.session.scalar(select(WaitlistEntry.name)) is None


@pytest.mark.parametrize("stage", ["execute", "commit", "connect"])
async def test_persistence_error_rolls_back_and_never_claims_success(client, isolated_db, stage):
    isolated_db.fail_at = stage
    response = await client.post("/api/v1/waitlist", json=VALID)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "WAITLIST_UNAVAILABLE"
    assert "internal database detail" not in response.text
    assert "9876543210" not in response.text
    assert isolated_db.rollbacks == 1
    assert isolated_db.session.scalar(select(func.count()).select_from(WaitlistEntry)) == 0


async def test_missing_database_configuration_is_a_safe_error():
    assert not get_settings().database_url
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/waitlist", json=VALID)
    assert response.status_code == 503
    assert "DATABASE_URL" not in response.text
    assert response.json()["error"]["code"] == "WAITLIST_UNAVAILABLE"


async def test_request_boundaries(client, isolated_db):
    malformed = await client.post(
        "/api/v1/waitlist", content="{", headers={"Content-Type": "application/json"}
    )
    assert malformed.status_code == 400
    wrong_type = await client.post("/api/v1/waitlist", content="plain text")
    assert wrong_type.status_code == 415
    oversized = await client.post(
        "/api/v1/waitlist", content=" " * 4097, headers={"Content-Type": "application/json"}
    )
    assert oversized.status_code == 413

    async def chunks():
        yield b" " * 3000
        yield b" " * 1097

    chunked = await client.post(
        "/api/v1/waitlist", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert chunked.status_code == 413
    assert isolated_db.statements == []
    assert (await client.get("/api/v1/waitlist")).status_code == 405


async def test_cors_allows_configured_origin_and_denies_unknown_origin(client):
    headers = {"Origin": ORIGIN, "Access-Control-Request-Method": "POST"}
    preflight = await client.options("/api/v1/waitlist", headers=headers)
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == ORIGIN
    result = await client.post("/api/v1/waitlist", headers={"Origin": ORIGIN}, json=VALID)
    assert result.headers["access-control-allow-origin"] == ORIGIN
    denied = await client.options(
        "/api/v1/waitlist", headers={**headers, "Origin": "https://untrusted.example"}
    )
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


async def test_health_still_runs_without_a_database(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_waitlist_does_not_call_booking_or_payment_operations(client, monkeypatch):
    from app.api.v1 import bookings
    from app.services.payments.gateway import RazorpayGateway

    async def forbidden(*args, **kwargs):
        raise AssertionError("Waitlist must not invoke booking or payment operations")

    monkeypatch.setattr(bookings, "initiate_booking", forbidden)
    monkeypatch.setattr(RazorpayGateway, "create_order", forbidden)
    response = await client.post("/api/v1/waitlist", json=VALID)
    assert response.status_code == 200


async def test_public_entry_point_exposes_only_waitlist_and_health(isolated_db):
    async def override():
        yield isolated_db

    public_waitlist_app.dependency_overrides[waitlist_database] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=public_waitlist_app), base_url="http://test"
        ) as public_client:
            assert (await public_client.get("/health")).status_code == 200
            assert (await public_client.post("/api/v1/waitlist", json=VALID)).status_code == 200
            assert (await public_client.get("/api/v1/merchants")).status_code == 404
            assert (await public_client.post("/api/v1/bookings", json={})).status_code == 404
            assert (await public_client.post("/api/v1/payments", json={})).status_code == 404
    finally:
        public_waitlist_app.dependency_overrides.pop(waitlist_database, None)


async def test_waitlist_rate_limit_is_per_client_and_expires():
    limit = WaitlistRateLimiter()
    for _ in range(60):
        await limit.check("client-one", now=1000)
    with pytest.raises(AppError) as error:
        await limit.check("client-one", now=1000)
    assert error.value.status_code == 429
    await limit.check("client-two", now=1000)
    await limit.check("client-one", now=1601)


def test_new_migration_only_creates_or_removes_waitlist_table():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/f93a4c1236de_add_waitlist_entries.py"
    )
    spec = importlib.util.spec_from_file_location("waitlist_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "e82f3b0125cd"
    config = Config()
    config.set_main_option("script_location", str(path.parents[1]))
    assert ScriptDirectory.from_config(config).get_heads() == ["a7d8c9012f34"]
    actions = [(migration.upgrade, "CREATE TABLE"), (migration.downgrade, "DROP TABLE")]
    for method, keyword in actions:
        output = StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            method()
        sql = output.getvalue()
        assert f"{keyword} waitlist_entries" in sql
        assert sql.count(keyword) == 1
        assert "ALTER TABLE" not in sql
        assert "bookings" not in sql and "payment" not in sql and "merchants" not in sql


def test_name_migration_only_changes_waitlist_table():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/a7d8c9012f34_add_waitlist_name.py"
    )
    spec = importlib.util.spec_from_file_location("waitlist_name_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "f93a4c1236de"
    actions = [(migration.upgrade, "ADD COLUMN"), (migration.downgrade, "DROP COLUMN")]
    for method, keyword in actions:
        output = StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            method()
        sql = output.getvalue()
        assert f"ALTER TABLE waitlist_entries {keyword} name" in sql
        assert sql.count("ALTER TABLE") == 1
        assert "bookings" not in sql and "payment" not in sql and "merchants" not in sql
