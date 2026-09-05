"""Small, dependency-light PostgreSQL connection helper.

The psycopg driver is imported only when a database connection is requested so
the default file-backed demo continues to run without PostgreSQL dependencies.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator


def database_configured() -> bool:
    """Return True when enough environment configuration exists to connect."""

    return bool(
        os.getenv("DATABASE_URL")
        or (os.getenv("DB_NAME") and os.getenv("DB_USER"))
    )


def connection_kwargs() -> dict[str, str | int]:
    values: dict[str, str | int] = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "ulpin"),
        "user": os.getenv("DB_USER", "postgres"),
    }
    password = os.getenv("DB_PASSWORD")
    if password:
        values["password"] = password
    return values


def connect():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(
            "PostGIS support requires psycopg. Install the optional database "
            "dependencies before selecting DATA_BACKEND=postgis."
        ) from exc

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url)
    return psycopg.connect(**connection_kwargs())


@contextmanager
def database_connection() -> Iterator[object]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def postgis_status() -> dict[str, object]:
    if not database_configured():
        return {
            "status": "CODE_READY",
            "configured": False,
            "operationally_tested": False,
            "detail": "Database environment variables are not configured.",
        }

    try:
        with database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT PostGIS_Version()")
                version = cursor.fetchone()[0]
        return {
            "status": "ACTIVE",
            "configured": True,
            "operationally_tested": True,
            "version": version,
        }
    except Exception as exc:  # pragma: no cover - environment-specific
        return {
            "status": "CODE_READY",
            "configured": True,
            "operationally_tested": False,
            "detail": str(exc),
        }
