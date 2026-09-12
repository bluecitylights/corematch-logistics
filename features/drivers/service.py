import duckdb
from typing import Generator, Sequence
from core.base_service import BaseService
from core.database import get_db
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate


class DriverService(BaseService):
    """Domain service for managing drivers."""

    def list_drivers(self, include_inactive: bool = False) -> Sequence[Driver]:
        where = "" if include_inactive else "WHERE is_active"
        return self.query_models(Driver, f"SELECT * FROM drivers {where} ORDER BY driver_id")

    def create_driver(self, payload: DriverCreate) -> Driver:
        self.execute(
            "INSERT INTO drivers (name, location_id, skill_adr, skill_ehbo, is_active) VALUES (?, ?, ?, ?, ?)",
            [payload.name, payload.location_id, payload.skill_adr, payload.skill_ehbo, payload.is_active],
        )
        drv = self.query_model_or_none(Driver, "SELECT * FROM drivers WHERE name = ?", [payload.name])
        if drv is None:
            raise ValueError("Failed to retrieve created driver")
        return drv

    def update_driver(self, driver_id: int, payload: DriverUpdate) -> Driver | None:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return self.query_model_or_none(Driver, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])
        
        self.execute_update("drivers", "driver_id", driver_id, fields)
        return self.query_model_or_none(Driver, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])

    def delete_driver(self, driver_id: int) -> Driver | None:
        return self.update_driver(driver_id, DriverUpdate(is_active=False))

    def count_active(self) -> int:
        rows = self.fetch_all("SELECT COUNT(*) FROM drivers WHERE is_active")
        return rows[0][0] if rows else 0


def get_driver_service() -> Generator[DriverService, None, None]:
    with get_db() as con:
        yield DriverService(con)


driver_service = DriverService()

list_drivers = driver_service.list_drivers
create_driver = driver_service.create_driver
update_driver = driver_service.update_driver
delete_driver = driver_service.delete_driver
count_active = driver_service.count_active