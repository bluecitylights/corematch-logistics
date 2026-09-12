from contextlib import contextmanager
from typing import Generator
import duckdb
from core.database import get_db, get_master_connection


class BaseService:
    """Base class for all domain service classes holding an active database connection/cursor."""

    def __init__(self, con: duckdb.DuckDBPyConnection | None = None):
        self._con = con

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is not None:
            return self._con
        return get_master_connection().cursor()

    @contextmanager
    def _get_con(self, con: duckdb.DuckDBPyConnection | None = None) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Yield the provided connection or this instance's connection/cursor."""
        if con is not None:
            yield con
        elif self._con is not None:
            yield self._con
        else:
            with get_db() as c:
                yield c
