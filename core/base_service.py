from contextlib import contextmanager
from typing import Generator, Any, Sequence, TypeVar, Type
import duckdb
from core.database import (
    get_db, 
    query_models as db_query_models, 
    query_model_or_none as db_query_model_or_none, 
    execute_update as db_execute_update,
    api_rows as db_api_rows
)

T = TypeVar("T")


class BaseService:
    """Base class for all domain service classes holding an active database connection/cursor."""

    def __init__(self, con: duckdb.DuckDBPyConnection | None = None):
        self._con = con

    @contextmanager
    def con(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Context manager that safely yields either the injected connection, 
        or a fresh cursor from the master connection via get_db(), ensuring proper cleanup.
        """
        if self._con is not None:
            yield self._con
        else:
            with get_db() as c:
                yield c

    def fetch_all(self, sql: str, params: list[Any] = None) -> list[tuple[Any, ...]]:
        with self.con() as con:
            return con.execute(sql, params or []).fetchall()

    def execute(self, sql: str, params: list[Any] = None) -> Any:
        with self.con() as con:
            return con.execute(sql, params or [])

    def executemany(self, sql: str, seq_of_parameters: Sequence[Sequence[Any]]) -> None:
        with self.con() as con:
            con.executemany(sql, seq_of_parameters)

    def query_models(self, model_class: Type[T], sql: str, params: list[Any] = None) -> Sequence[T]:
        with self.con() as con:
            return db_query_models(model_class, con, sql, params or [])

    def query_model_or_none(self, model_class: Type[T], sql: str, params: list[Any] = None) -> T | None:
        with self.con() as con:
            return db_query_model_or_none(model_class, con, sql, params or [])

    def execute_update(self, table: str, id_column: str, id_value: Any, fields: dict[str, Any]) -> None:
        with self.con() as con:
            db_execute_update(table, id_column, id_value, fields, con=con)

    def api_rows(self, sql: str, params: list[Any] = None) -> list[dict[str, Any]]:
        with self.con() as con:
            return db_api_rows(con, sql, params or [])