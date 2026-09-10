"""Shared DuckDB configuration and query helpers."""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import duckdb
from fastapi import HTTPException

from engine import init_schema
from db.locations import ensure_location_schema


DB_PATH = os.environ.get(
    "DB_PATH",
    str(Path(__file__).parent.parent / "data" / "corematch.duckdb"),
)


@contextmanager
def get_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(DB_PATH, read_only=False)
    try:
        yield con
    finally:
        con.close()


def ensure_schema() -> None:
    with get_db() as con:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        if "drivers" not in tables:
            init_schema(con)
        ensure_location_schema(con)
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                plan_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_orders (
                plan_id VARCHAR NOT NULL,
                order_id VARCHAR NOT NULL,
                driver_id VARCHAR,
                vehicle_id VARCHAR,
                stop_sequence INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (plan_id, order_id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS plan_evaluations (
                plan_id VARCHAR NOT NULL,
                order_id VARCHAR NOT NULL,
                driver_id VARCHAR NOT NULL,
                vehicle_id VARCHAR NOT NULL,
                stop_sequence INTEGER NOT NULL,
                origin_zip VARCHAR NOT NULL,
                destination_zip VARCHAR NOT NULL,
                driving_time_min INTEGER NOT NULL,
                departure_time VARCHAR NOT NULL,
                arrival_time VARCHAR NOT NULL,
                PRIMARY KEY (plan_id, order_id)
            )
            """
        )


def api_rows(
    con: duckdb.DuckDBPyConnection,
    query: str,
    parameters: list[Any] | None = None,
) -> list[dict[str, Any]]:
    result = con.execute(query, parameters or [])
    columns = [column[0] for column in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def api_update(
    table: str,
    identifier_column: str,
    identifier: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    if not fields:
        raise HTTPException(400, "At least one editable field is required")
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with get_db() as con:
        con.execute(
            f"UPDATE {table} SET {assignments} WHERE {identifier_column} = ?",
            list(fields.values()) + [identifier],
        )
        rows = api_rows(
            con,
            f"SELECT * FROM {table} WHERE {identifier_column} = ?",
            [identifier],
        )
        if not rows:
            raise HTTPException(404, f"{table[:-1].capitalize()} not found: {identifier}")
        return rows[0]
