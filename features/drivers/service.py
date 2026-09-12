import duckdb
from typing import Any, Sequence
from core.base_service import BaseService
from core.database import query_models, execute_update, query_model_or_none
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate


class DriverService(BaseService):
    """Domain service for managing drivers."""

    def list_drivers(self, arg1: Any = None, include_inactive: bool = False, con: duckdb.DuckDBPyConnection | None = None) -> Sequence[Driver]:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
        else:
            if isinstance(arg1, bool):
                include_inactive = arg1
            c_passed = con
        where = "" if include_inactive else "WHERE is_active"
        with self._get_con(c_passed) as c:
            return query_models(Driver, c, f"SELECT * FROM drivers {where} ORDER BY driver_index")

    def create_driver(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Driver:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            payload = arg2
        else:
            payload = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            c.execute(
                "INSERT INTO drivers (driver_id, location_id, skill_adr, skill_ehbo, is_active) VALUES (?, ?, ?, ?, ?)",
                [payload.driver_id, payload.location_id, payload.skill_adr, payload.skill_ehbo, payload.is_active],
            )
            drv = query_model_or_none(Driver, c, "SELECT * FROM drivers WHERE driver_id = ?", [payload.driver_id])
            if drv is None:
                raise ValueError("Failed to retrieve created driver")
            return drv

    def update_driver(self, arg1: Any, arg2: Any, arg3: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Driver | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            driver_id = arg2
            payload = arg3
        else:
            driver_id = arg1
            payload = arg2
            c_passed = con or (arg3 if isinstance(arg3, duckdb.DuckDBPyConnection) else None)
        fields = payload.model_dump(exclude_unset=True)
        with self._get_con(c_passed) as c:
            if not fields:
                return query_model_or_none(Driver, c, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])
            execute_update("drivers", "driver_id", driver_id, fields, con=c)
            return query_model_or_none(Driver, c, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])

    def delete_driver(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Driver | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            driver_id = arg2
        else:
            driver_id = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        return self.update_driver(driver_id, DriverUpdate(is_active=False), con=c_passed)

    def count_active(self, con: duckdb.DuckDBPyConnection | None = None) -> int:
        with self._get_con(con) as c:
            row = c.execute("SELECT COUNT(*) FROM drivers WHERE is_active").fetchone()
            return row[0] if row else 0


driver_service = DriverService()

# Backward-compatibility aliases
list_drivers = driver_service.list_drivers
create_driver = driver_service.create_driver
update_driver = driver_service.update_driver
delete_driver = driver_service.delete_driver
count_active = driver_service.count_active

