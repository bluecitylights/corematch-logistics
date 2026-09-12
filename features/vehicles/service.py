import duckdb
from typing import Sequence
from core.database import query_models, execute_update, query_model_or_none
from features.vehicles.schemas import Vehicle, VehicleCreate, VehicleUpdate

def list_vehicles(con: duckdb.DuckDBPyConnection, include_inactive: bool = False) -> Sequence[Vehicle]:
    where = "" if include_inactive else "WHERE is_active"
    return query_models(Vehicle, con, f"SELECT * FROM vehicles {where} ORDER BY vehicle_index")

def create_vehicle(con: duckdb.DuckDBPyConnection, payload: VehicleCreate) -> Vehicle:
    con.execute(
        "INSERT INTO vehicles (vehicle_id, license_plate, location_id, spec_liftgate, spec_refrigerated, is_active) VALUES (?, ?, ?, ?, ?, ?)",
        [payload.vehicle_id, payload.license_plate, payload.location_id, payload.spec_liftgate, payload.spec_refrigerated, payload.is_active],
    )
    veh = query_model_or_none(Vehicle, con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id])
    if veh is None:
        raise ValueError("Failed to retrieve created vehicle")
    return veh

def update_vehicle(con: duckdb.DuckDBPyConnection, vehicle_id: str, payload: VehicleUpdate) -> Vehicle | None:
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return query_model_or_none(Vehicle, con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])
    
    execute_update("vehicles", "vehicle_id", vehicle_id, fields, con=con)
    return query_model_or_none(Vehicle, con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])

def delete_vehicle(con: duckdb.DuckDBPyConnection, vehicle_id: str) -> Vehicle | None:
    return update_vehicle(con, vehicle_id, VehicleUpdate(is_active=False))

