import duckdb
from typing import Sequence
from core.database import query_models, execute_update, query_model_or_none, api_rows
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate

def list_drivers(con: duckdb.DuckDBPyConnection, include_inactive: bool = False) -> Sequence[Driver]:
    where = "" if include_inactive else "WHERE is_active"
    return query_models(Driver, con, f"SELECT * FROM drivers {where} ORDER BY driver_index")

def create_driver(con: duckdb.DuckDBPyConnection, payload: DriverCreate) -> Driver:
    con.execute(
        "INSERT INTO drivers (driver_id, location_id, skill_adr, skill_ehbo, is_active) VALUES (?, ?, ?, ?, ?)",
        [payload.driver_id, payload.location_id, payload.skill_adr, payload.skill_ehbo, payload.is_active],
    )
    drv = query_model_or_none(Driver, con, "SELECT * FROM drivers WHERE driver_id = ?", [payload.driver_id])
    if drv is None:
        raise ValueError("Failed to retrieve created driver")
    return drv

def update_driver(con: duckdb.DuckDBPyConnection, driver_id: str, payload: DriverUpdate) -> Driver | None:
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return query_model_or_none(Driver, con, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])
    
    execute_update("drivers", "driver_id", driver_id, fields, con=con)
    return query_model_or_none(Driver, con, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])

def delete_driver(con: duckdb.DuckDBPyConnection, driver_id: str) -> Driver | None:
    return update_driver(con, driver_id, DriverUpdate(is_active=False))

