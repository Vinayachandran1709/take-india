import importlib.util
from io import StringIO
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_trial_reminder_migration_is_additive_and_reversible():
    path = Path(__file__).resolve().parents[1] / (
        "alembic/versions/a81d7e4c902b_trial_reminder_deliveries.py"
    )
    spec = importlib.util.spec_from_file_location("trial_reminder_migration", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "f6a2c1e9d803"

    def sql(operation):
        output = StringIO()
        context = MigrationContext.configure(
            dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
        )
        with Operations.context(context):
            operation()
        return output.getvalue()

    upgrade = sql(migration.upgrade)
    downgrade = sql(migration.downgrade)
    assert "CREATE TABLE trial_reminder_deliveries" in upgrade
    assert "PRIMARY KEY (merchant_id, kind)" in upgrade
    assert "FOREIGN KEY(merchant_id) REFERENCES merchants" in upgrade
    assert "DROP TABLE trial_reminder_deliveries" in downgrade
