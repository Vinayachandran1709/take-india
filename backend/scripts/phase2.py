"""Guarded local Phase 2 entry point. Never target the Phase 1 or test database."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import dotenv_values

from app.core.test_safety import database_identity


def phase2_environment() -> dict[str, str]:
    source = Path(".env.phase2")
    if not source.is_file():
        raise RuntimeError(
            "Create backend/.env.phase2 with the separate Neon phase2-dev URLs first"
    )
    values = dotenv_values(source)
    original = dotenv_values(".env")
    missing = [
        name for name in ("DATABASE_URL", "DIRECT_DATABASE_URL") if not values.get(name)
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Set {joined} in backend/.env.phase2 from the separate Neon phase2-dev branch"
        )
    try:
        pooled = database_identity(values["DATABASE_URL"])
        direct = database_identity(values["DIRECT_DATABASE_URL"])
        if pooled != direct:
            raise ValueError
        for name in ("DATABASE_URL", "DIRECT_DATABASE_URL", "TEST_DATABASE_URL"):
            if original.get(name) and pooled == database_identity(original[name]):
                raise ValueError
        if values.get("TEST_DATABASE_URL") and pooled == database_identity(
            values["TEST_DATABASE_URL"]
        ):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise RuntimeError(
            "Phase 2 must use one separate database, distinct from Phase 1 and test"
        ) from None
    try:
        Fernet(values.get("CREDENTIAL_ENCRYPTION_KEY", "").encode())
        if not values.get("JWT_SECRET_KEY"):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("Set valid local CREDENTIAL_ENCRYPTION_KEY and JWT_SECRET_KEY") from None
    environment = os.environ.copy()
    environment.update({key: value for key, value in values.items() if value is not None})
    environment["ENVIRONMENT"] = "development"
    environment["TAKE_INDIA_ENV_FILE"] = str(source.resolve())
    return environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "migrate", "serve", "seed"])
    args = parser.parse_args()
    try:
        environment = phase2_environment()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    if args.action == "check":
        print(
            "Phase 2 environment identity and credential-key guards passed (no secrets displayed)"
        )
        return
    commands = {
        "migrate": ["alembic", "upgrade", "head"],
        "serve": ["uvicorn", "app.phase2_main:app", "--host", "127.0.0.1", "--port", "8000"],
        "seed": ["scripts.seed"],
    }
    raise SystemExit(
        subprocess.call([sys.executable, "-m", *commands[args.action]], env=environment)
    )


if __name__ == "__main__":
    main()
