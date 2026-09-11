from contextlib import contextmanager
from typing import Any, TypeVar
import duckdb
from pydantic import BaseModel
from core.config import DB_PATH, SCHEMA_PATH

T = TypeVar("T", bound=BaseModel)

@contextmanager
def get_db(db_path: str = DB_PATH):
    con = duckdb.connect(db_path)
    try:
        yield con
    finally:
        con.close()

def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA_PATH.read_text())

def api_rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cursor = con.execute(sql, params or [])
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def query_models(model_cls: type[T], con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[T]:
    rows = api_rows(con, sql, params)
    return [model_cls.model_validate(row) for row in rows]

def query_model_or_none(model_cls: type[T], con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> T | None:
    models = query_models(model_cls, con, sql, params)
    return models[0] if models else None

def execute_update(table: str, key_col: str, key_val: Any, fields: dict[str, Any], con: duckdb.DuckDBPyConnection | None = None) -> dict[str, Any]:
    if not fields:
        raise ValueError("No fields to update")
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    params = list(fields.values()) + [key_val]
    
    def _run(c):
        c.execute(f"UPDATE {table} SET {set_clause} WHERE {key_col} = ?", params)
        rows = api_rows(c, f"SELECT * FROM {table} WHERE {key_col} = ?", [key_val])
        if not rows:
            raise KeyError(f"{table} with {key_col}={key_val} not found")
        return rows[0]

    if con is not None:
        return _run(con)
    with get_db() as c:
        return _run(c)

