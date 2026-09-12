import duckdb
from typing import Generator, Sequence
from core.base_service import BaseService
from core.database import get_db, query_models, execute_update, query_model_or_none
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate


class DriverService(BaseService):
    """Domain service for managing drivers."""

    def list_drivers(self, include_inactive: bool = False) -> Sequence[Driver]:
        where = "" if include_inactive else "WHERE is_active"
        return query_models(Driver, self.con, f"SELECT * FROM drivers {where} ORDER BY driver_index")

    def create_driver(self, payload: DriverCreate) -> Driver:
        self.con.execute(
            "INSERT INTO drivers (driver_id, location_id, skill_adr, skill_ehbo, is_active) VALUES (?, ?, ?, ?, ?)",
            [payload.driver_id, payload.location_id, payload.skill_adr, payload.skill_ehbo, payload.is_active],
        )
        drv = query_model_or_none(Driver, self.con, "SELECT * FROM drivers WHERE driver_id = ?", [payload.driver_id])
        if drv is None:
            raise ValueError("Failed to retrieve created driver")
        return drv

    def update_driver(self, driver_id: str, payload: DriverUpdate) -> Driver | None:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return query_model_or_none(Driver, self.con, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])
        execute_update("drivers", "driver_id", driver_id, fields, con=self.con)
        return query_model_or_none(Driver, self.con, "SELECT * FROM drivers WHERE driver_id = ?", [driver_id])

    def delete_driver(self, driver_id: str) -> Driver | None:
        return self.update_driver(driver_id, DriverUpdate(is_active=False))

    def count_active(self) -> int:
        row = self.con.execute("SELECT COUNT(*) FROM drivers WHERE is_active").fetchone()
        return row[0] if row else 0


def get_driver_service() -> Generator[DriverService, None, None]:
    with get_db() as con:
        yield DriverService(con)


driver_service = DriverService()
