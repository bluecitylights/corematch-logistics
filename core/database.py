import threading
from contextlib import contextmanager
from typing import Any, TypeVar
import duckdb
from pydantic import BaseModel
from core.config import DB_PATH, SCHEMA_PATH

T = TypeVar("T", bound=BaseModel)

_MASTER_LOCK = threading.Lock()
_MASTER_CON: duckdb.DuckDBPyConnection | None = None
_CURRENT_DB_PATH: str | None = None


def get_master_connection(db_path: str = DB_PATH) -> duckdb.DuckDBPyConnection:
    """Return the thread-safe master DuckDB connection for the specified db_path."""
    global _MASTER_CON, _CURRENT_DB_PATH
    with _MASTER_LOCK:
        if _MASTER_CON is None or _CURRENT_DB_PATH != db_path:
            if _MASTER_CON is not None:
                try:
                    _MASTER_CON.close()
                except Exception:
                    pass
            _MASTER_CON = duckdb.connect(db_path)
            _CURRENT_DB_PATH = db_path
        return _MASTER_CON


def close_master_connection() -> None:
    """Close the master connection if open."""
    global _MASTER_CON, _CURRENT_DB_PATH
    with _MASTER_LOCK:
        if _MASTER_CON is not None:
            try:
                _MASTER_CON.close()
            except Exception:
                pass
            _MASTER_CON = None
            _CURRENT_DB_PATH = None


def set_master_connection(con: duckdb.DuckDBPyConnection | None) -> None:
    """Explicitly set or reset the master connection (e.g. for testing)."""
    global _MASTER_CON, _CURRENT_DB_PATH
    with _MASTER_LOCK:
        _MASTER_CON = con
        _CURRENT_DB_PATH = None



@contextmanager
def get_db(db_path: str = DB_PATH):
    """
    Yield a thread-safe cursor from the master connection.
    If db_path is ':memory:', opens a dedicated connection for that memory DB context.
    """
    if db_path == ":memory:":
        con = duckdb.connect(db_path)
        try:
            yield con
        finally:
            con.close()
    else:
        master = get_master_connection(db_path)
        cursor = master.cursor()
        try:
            yield cursor
        finally:
            cursor.close()


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


def seed_demo(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """Insert a small representative dataset for a quick smoke-test."""
    if con is None:
        with get_db() as c:
            seed_demo(c)
        return

    demo_locations = [
        ("1012", "Amsterdam", 52.3728, 4.8936),
        ("3011", "Rotterdam", 51.9244, 4.4777),
        ("3511", "Utrecht", 52.0907, 5.1214),
    ]
    con.executemany(
        """
        INSERT INTO locations (zip, city, latitude, longitude)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (zip) DO NOTHING
        """,
        demo_locations,
    )
    location_indices = {
        city: location_index
        for location_index, city in con.execute(
            "SELECT location_index, city FROM locations WHERE city IN ('Amsterdam', 'Rotterdam', 'Utrecht')"
        ).fetchall()
    }
    con.executemany(
        "INSERT INTO drivers (name, location_index, is_active, skill_adr, skill_ehbo) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("DRV-001", location_indices["Amsterdam"], True, True, False),
            ("DRV-002", location_indices["Amsterdam"], True, False, True),
            ("DRV-003", location_indices["Rotterdam"], True, True, True),
            ("DRV-004", location_indices["Utrecht"], True, False, False),
            ("DRV-005", location_indices["Amsterdam"], False, True, True),
        ],
    )
    con.executemany(
        "INSERT INTO vehicles (vehicle_id, license_plate, location_index, is_active, "
        "spec_liftgate, spec_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("VEH-001", "AB-12-CD", location_indices["Amsterdam"], True, True, False),
            ("VEH-002", "EF-34-GH", location_indices["Amsterdam"], True, False, True),
            ("VEH-003", "IJ-56-KL", location_indices["Rotterdam"], True, True, True),
            ("VEH-004", "MN-78-OP", location_indices["Utrecht"], True, False, False),
        ],
    )
    con.executemany(
        "INSERT INTO orders (order_id, destination_location_index, req_driver_adr, req_driver_ehbo, "
        "req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ORD-001", location_indices["Amsterdam"], True, False, True, False),
            ("ORD-002", location_indices["Amsterdam"], False, True, False, True),
            ("ORD-003", location_indices["Rotterdam"], False, False, False, False),
            ("ORD-004", location_indices["Rotterdam"], True, True, False, False),
            ("ORD-005", location_indices["Utrecht"], True, False, False, False),
        ],
    )