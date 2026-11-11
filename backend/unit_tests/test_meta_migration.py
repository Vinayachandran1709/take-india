import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_meta_inbox_migration_is_additive_and_reversible() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/e913f6b2a004_meta_webhook_inbox.py"
    )
    spec = importlib.util.spec_from_file_location("meta_inbox_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "d4c2e6a91b70"

    def render(operation):
        output = StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            operation()
        return output.getvalue()

    upgrade = render(migration.upgrade)
    downgrade = render(migration.downgrade)
    assert "CREATE TABLE meta_webhook_events" in upgrade
    assert "CREATE INDEX ix_meta_webhook_events_received_at" in upgrade
    assert "DROP TABLE" not in upgrade
    assert "DROP TABLE meta_webhook_events" in downgrade
    assert "merchants" not in downgrade and "bookings" not in downgrade
