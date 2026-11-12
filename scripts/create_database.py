#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402


def main() -> int:
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("mssql+pyodbc"):
        print("Skipping database creation: DATABASE_URL is not mssql+pyodbc.", file=sys.stderr)
        return 0
    if not url.database:
        print("Skipping database creation: DATABASE_URL has no database name.", file=sys.stderr)
        return 1

    database = url.database
    master_url = url.set(database="master")
    quoted = f"[{database.replace(']', ']]')}]"
    literal = database.replace("'", "''")
    statement = f"IF DB_ID(N'{literal}') IS NULL CREATE DATABASE {quoted}"

    engine = create_engine(master_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(text(statement))
    finally:
        engine.dispose()

    print(f"Database '{database}' is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
