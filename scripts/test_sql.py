#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ----------------------------
# Paths (robust for CI)
# ----------------------------
ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def load_env() -> None:
    # Explicit path avoids python-dotenv edge cases with stdin/heredocs
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH)
    else:
        # In CI you might not have .env; env vars are set by the runner.
        load_dotenv()

    if "DATABASE_URL" not in os.environ:
        raise RuntimeError(
            "DATABASE_URL is not set. Create .env with DATABASE_URL=... or set it in your environment."
        )


def get_engine() -> Engine:
    url = os.environ["DATABASE_URL"]
    return create_engine(url, future=True)


def run_schema(engine: Engine, schema_path: Path) -> None:
    if not schema_path.exists():
        raise FileNotFoundError(f"schema file not found: {schema_path}")

    sql = schema_path.read_text(encoding="utf-8")

    # Run everything in one transaction
    with engine.begin() as conn:
        # split on ; is risky for functions, but your schema is normal DDL.
        # Execute as one string — postgres/psycopg2 handles it fine.
        conn.exec_driver_sql(sql)


def sanity_check(engine: Engine) -> None:
    # Very lightweight sanity checks (you can expand later)
    with engine.connect() as conn:
        one = conn.execute(text("SELECT 1")).scalar_one()
        assert one == 1

        # Count tables in public schema
        tables = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name;
                """
            )
        ).fetchall()

    if not tables:
        raise RuntimeError("No tables found after applying schema.sql")

    print(f"✅ Connected and found {len(tables)} tables.")
    # Uncomment if you want to print them:
    # for (t,) in tables:
    #     print(" -", t)


def main() -> int:
    load_env()
    engine = get_engine()

    print(f"Using DB URL: {os.environ['DATABASE_URL']}")
    print("[1/2] Applying db/schema.sql ...")
    run_schema(engine, SCHEMA_PATH)
    print("[2/2] Sanity checks ...")
    sanity_check(engine)

    print("✅ ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
