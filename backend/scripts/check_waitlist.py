"""Run database-free waitlist checks and existing payment unit regressions safely."""

import os
import sys
from pathlib import Path

import pytest


def main() -> int:
    backend = Path(__file__).resolve().parents[1]
    absent_env = backend / ".waitlist-tests-no-env"
    if absent_env.exists():
        raise RuntimeError("The isolated test environment sentinel must not exist.")
    # Applies only to this process. Never load existing .env files or use their databases.
    os.environ.update(
        {
            "TAKE_INDIA_ENV_FILE": str(absent_env),
            "DATABASE_URL": "",
            "DIRECT_DATABASE_URL": "",
            "TEST_DATABASE_URL": "",
            "ALLOW_TEST_DATABASE_RESET": "false",
            "ENVIRONMENT": "test",
            "JWT_SECRET_KEY": "",
            "CREDENTIAL_ENCRYPTION_KEY": "",
            "CORS_ORIGINS": (
                "http://127.0.0.1:4173,http://localhost:3000,http://localhost:5173"
            ),
        }
    )
    sys.dont_write_bytecode = True
    return pytest.main(
        [
            "-q",
            "-p",
            "no:cacheprovider",
            # This unrelated regression needs pytest's temp-file fixture, which is
            # inaccessible in the audited Windows environment. Do not alter its ACLs.
            "-k",
            "not test_local_phase2_guard_rejects_phase1_and_test_aliases",
            str(backend / "unit_tests/test_waitlist.py"),
            str(backend / "unit_tests/test_payment_security.py"),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
