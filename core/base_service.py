from contextlib import contextmanager
from typing import Any, Callable, Generator
import duckdb

from core.database import get_db


class BaseService:
    """Base class for all domain service classes to manage database connection lifecycle."""

    def __init__(self, db_factory: Callable[[], Any] = get_db):
        self._db_factory = db_factory

    @contextmanager
    def _get_con(self, con: duckdb.DuckDBPyConnection | None = None) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Yield the provided connection or obtain and close a connection from the factory."""
        if con is not None:
            yield con
        else:
            with self._db_factory() as new_con:
                yield new_con
