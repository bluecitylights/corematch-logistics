import duckdb
from typing import Any, Generator, Sequence
from core.base_service import BaseService
from core.database import get_db, query_models, execute_update, query_model_or_none
from features.vehicles.schemas import Vehicle, VehicleCreate, VehicleUpdate


class VehicleService(BaseService):
    """Domain service for managing vehicles."""

    def list_vehicles(self, arg1: Any = None, include_inactive: bool = False) -> Sequence[Vehicle]:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
        else:
            c = self.con
            if isinstance(arg1, bool):
                include_inactive = arg1
        where = "" if include_inactive else "WHERE is_active"
        return query_models(Vehicle, c, f"SELECT * FROM vehicles {where} ORDER BY vehicle_index")

    def create_vehicle(self, arg1: Any, arg2: Any = None) -> Vehicle:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
            payload = arg2
        else:
            c = self.con
            payload = arg1
        c.execute(
            "INSERT INTO vehicles (vehicle_id, license_plate, location_id, spec_liftgate, spec_refrigerated, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.vehicle_id, payload.license_plate, payload.location_id, payload.spec_liftgate, payload.spec_refrigerated, payload.is_active],
        )
        veh = query_model_or_none(Vehicle, c, "SELECT * FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id])
        if veh is None:
            raise ValueError("Failed to retrieve created vehicle")
        return veh

    def update_vehicle(self, arg1: Any, arg2: Any, arg3: Any = None) -> Vehicle | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
            vehicle_id = arg2
            payload = arg3
        else:
            c = self.con
            vehicle_id = arg1
            payload = arg2
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return query_model_or_none(Vehicle, c, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])
        execute_update("vehicles", "vehicle_id", vehicle_id, fields, con=c)
        return query_model_or_none(Vehicle, c, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])

    def delete_vehicle(self, arg1: Any, arg2: Any = None) -> Vehicle | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
            vehicle_id = arg2
        else:
            c = self.con
            driver_id = arg1
        return self.update_vehicle(c, vehicle_id if isinstance(arg1, duckdb.DuckDBPyConnection) else arg1, VehicleUpdate(is_active=False))

    def count_active(self, con: duckdb.DuckDBPyConnection | None = None) -> int:
        c = con or self.con
        row = c.execute("SELECT COUNT(*) FROM vehicles WHERE is_active").fetchone()
        return row[0] if row else 0


def get_vehicle_service() -> Generator[VehicleService, None, None]:
    with get_db() as con:
        yield VehicleService(con)


vehicle_service = VehicleService()

# Backward-compatibility aliases
list_vehicles = vehicle_service.list_vehicles
create_vehicle = vehicle_service.create_vehicle
update_vehicle = vehicle_service.update_vehicle
delete_vehicle = vehicle_service.delete_vehicle
count_active = vehicle_service.count_active
