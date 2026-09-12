import duckdb
from typing import Generator, Sequence
from core.base_service import BaseService
from core.database import get_db, query_models, execute_update, query_model_or_none
from features.vehicles.schemas import Vehicle, VehicleCreate, VehicleUpdate


class VehicleService(BaseService):
    """Domain service for managing vehicles."""

    def list_vehicles(self, include_inactive: bool = False) -> Sequence[Vehicle]:
        where = "" if include_inactive else "WHERE is_active"
        return query_models(Vehicle, self.con, f"SELECT * FROM vehicles {where} ORDER BY vehicle_index")

    def create_vehicle(self, payload: VehicleCreate) -> Vehicle:
        self.con.execute(
            "INSERT INTO vehicles (vehicle_id, license_plate, location_id, spec_liftgate, spec_refrigerated, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.vehicle_id, payload.license_plate, payload.location_id, payload.spec_liftgate, payload.spec_refrigerated, payload.is_active],
        )
        veh = query_model_or_none(Vehicle, self.con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id])
        if veh is None:
            raise ValueError("Failed to retrieve created vehicle")
        return veh

    def update_vehicle(self, vehicle_id: str, payload: VehicleUpdate) -> Vehicle | None:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return query_model_or_none(Vehicle, self.con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])
        execute_update("vehicles", "vehicle_id", vehicle_id, fields, con=self.con)
        return query_model_or_none(Vehicle, self.con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [vehicle_id])

    def delete_vehicle(self, vehicle_id: str) -> Vehicle | None:
        return self.update_vehicle(vehicle_id, VehicleUpdate(is_active=False))

    def count_active(self) -> int:
        row = self.con.execute("SELECT COUNT(*) FROM vehicles WHERE is_active").fetchone()
        return row[0] if row else 0


def get_vehicle_service() -> Generator[VehicleService, None, None]:
    with get_db() as con:
        yield VehicleService(con)


vehicle_service = VehicleService()

list_vehicles = vehicle_service.list_vehicles
create_vehicle = vehicle_service.create_vehicle
update_vehicle = vehicle_service.update_vehicle
delete_vehicle = vehicle_service.delete_vehicle
count_active = vehicle_service.count_active
