import duckdb
from typing import Any, Sequence
from core.base_service import BaseService
from core.database import query_models, execute_update, query_model_or_none
from features.vehicles.schemas import Vehicle, VehicleCreate, VehicleUpdate


class VehicleService(BaseService):
    """Domain service for managing vehicles."""

    def list_vehicles(self, arg1: Any = None, include_inactive: bool = False, con: duckdb.DuckDBPyConnection | None = None) -> Sequence[Vehicle]:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
        else:
            if isinstance(arg1, bool):
                include_inactive = arg1
            c_passed = con
        where = "" if include_inactive else "WHERE is_active"
        with self._get_con(c_passed) as c:
            return query_models(Vehicle, c, f"SELECT * FROM vehicles {where} ORDER BY vehicle_index")

    def create_vehicle(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Vehicle:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            payload = arg2
        else:
            payload = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            c.execute(
                "INSERT INTO vehicles (vehicle_id, license_plate, location_id, spec_liftgate, spec_refrigerated, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                [payload.vehicle_id, payload.license_plate, payload.location_id, payload.spec_liftgate, payload.spec_refrigerated, payload.is_active],
            )
            veh = query_model_or_none(Vehicle, c, "SELECT * FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id])
            if veh is None:
                raise ValueError("Failed to retrieve created vehicle")
            return veh

    def update_vehicle(self, arg1: Any, arg2: Any, arg3: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Vehicle | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            vehicle_id = arg2
            payload = arg3
        else:
            vehicle_id = arg1
            payload = arg2
            c_passed = con or (arg3 if isinstance(arg3, duckdb.DuckDBPyConnection) else None)
        fields = payload.model_dump(exclude_unset=True)
        with self._get_con(c_passed) as c:
            if not fields:
                return query_model_or_none(Vehicle, c, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])
            execute_update("vehicles", "vehicle_id", vehicle_id, fields, con=c)
            return query_model_or_none(Vehicle, c, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])

    def delete_vehicle(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Vehicle | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            vehicle_id = arg2
        else:
            vehicle_id = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        return self.update_vehicle(vehicle_id, VehicleUpdate(is_active=False), con=c_passed)

    def count_active(self, con: duckdb.DuckDBPyConnection | None = None) -> int:
        with self._get_con(con) as c:
            row = c.execute("SELECT COUNT(*) FROM vehicles WHERE is_active").fetchone()
            return row[0] if row else 0


vehicle_service = VehicleService()

# Backward-compatibility aliases
list_vehicles = vehicle_service.list_vehicles
create_vehicle = vehicle_service.create_vehicle
update_vehicle = vehicle_service.update_vehicle
delete_vehicle = vehicle_service.delete_vehicle
count_active = vehicle_service.count_active

