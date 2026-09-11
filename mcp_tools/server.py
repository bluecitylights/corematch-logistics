"""FastMCP tools wrapping CoreMatch-Logistics vertical slice services."""

from typing import Any
import duckdb
from fastmcp import FastMCP

from core.database import get_db
from features.locations import service as location_service, schemas as location_schemas
from features.drivers import service as driver_service, schemas as driver_schemas
from features.vehicles import service as vehicle_service, schemas as vehicle_schemas
from features.orders import service as order_service, schemas as order_schemas
from features.plans import service as plan_service, schemas as plan_schemas
from features.matching import engine as matching_engine

mcp = FastMCP("CoreMatch-Logistics")

def _dict(obj):
    return obj.model_dump() if hasattr(obj, "model_dump") else obj

@mcp.tool
def list_drivers(include_inactive: bool = False) -> list[dict[str, Any]]:
    """List drivers directly via domain service."""
    with get_db() as con:
        return [_dict(d) for d in driver_service.list_drivers(con, include_inactive=include_inactive)]

@mcp.tool
def create_driver(driver_id: str, location_id: int, skill_adr: bool = False, skill_ehbo: bool = False) -> dict[str, Any]:
    with get_db() as con:
        payload = driver_schemas.DriverCreate(driver_id=driver_id, location_id=location_id, skill_adr=skill_adr, skill_ehbo=skill_ehbo)
        return _dict(driver_service.create_driver(con, payload))

@mcp.tool
def update_driver(driver_id: str, location_id: int | None = None, is_active: bool | None = None, skill_adr: bool | None = None, skill_ehbo: bool | None = None) -> dict[str, Any]:
    with get_db() as con:
        payload = driver_schemas.DriverUpdate(location_id=location_id, is_active=is_active, skill_adr=skill_adr, skill_ehbo=skill_ehbo)
        return _dict(driver_service.update_driver(con, driver_id, payload))

@mcp.tool
def delete_driver(driver_id: str) -> dict[str, Any]:
    with get_db() as con:
        return _dict(driver_service.delete_driver(con, driver_id))

@mcp.tool
def list_vehicles(include_inactive: bool = False) -> list[dict[str, Any]]:
    with get_db() as con:
        return [_dict(v) for v in vehicle_service.list_vehicles(con, include_inactive=include_inactive)]

@mcp.tool
def create_vehicle(vehicle_id: str, license_plate: str, location_id: int, spec_liftgate: bool = False, spec_refrigerated: bool = False) -> dict[str, Any]:
    with get_db() as con:
        payload = vehicle_schemas.VehicleCreate(vehicle_id=vehicle_id, license_plate=license_plate, location_id=location_id, spec_liftgate=spec_liftgate, spec_refrigerated=spec_refrigerated)
        return _dict(vehicle_service.create_vehicle(con, payload))

@mcp.tool
def update_vehicle(vehicle_id: str, license_plate: str | None = None, location_id: int | None = None, is_active: bool | None = None, spec_liftgate: bool | None = None, spec_refrigerated: bool | None = None) -> dict[str, Any]:
    with get_db() as con:
        payload = vehicle_schemas.VehicleUpdate(license_plate=license_plate, location_id=location_id, is_active=is_active, spec_liftgate=spec_liftgate, spec_refrigerated=spec_refrigerated)
        return _dict(vehicle_service.update_vehicle(con, vehicle_id, payload))

@mcp.tool
def delete_vehicle(vehicle_id: str) -> dict[str, Any]:
    with get_db() as con:
        return _dict(vehicle_service.delete_vehicle(con, vehicle_id))

@mcp.tool
def list_orders() -> list[dict[str, Any]]:
    with get_db() as con:
        return [_dict(o) for o in order_service.list_orders(con)]

@mcp.tool
def create_order(order_id: str, destination_location_id: int, req_driver_adr: bool = False, req_driver_ehbo: bool = False, req_vehicle_liftgate: bool = False, req_vehicle_refrigerated: bool = False) -> dict[str, Any]:
    with get_db() as con:
        payload = order_schemas.OrderCreate(order_id=order_id, destination_location_id=destination_location_id, req_driver_adr=req_driver_adr, req_driver_ehbo=req_driver_ehbo, req_vehicle_liftgate=req_vehicle_liftgate, req_vehicle_refrigerated=req_vehicle_refrigerated)
        return _dict(order_service.create_order(con, payload))

@mcp.tool
def update_order(order_id: str, destination_location_id: int | None = None, req_driver_adr: bool | None = None, req_driver_ehbo: bool | None = None, req_vehicle_liftgate: bool | None = None, req_vehicle_refrigerated: bool | None = None) -> dict[str, Any]:
    with get_db() as con:
        payload = order_schemas.OrderUpdate(destination_location_id=destination_location_id, req_driver_adr=req_driver_adr, req_driver_ehbo=req_driver_ehbo, req_vehicle_liftgate=req_vehicle_liftgate, req_vehicle_refrigerated=req_vehicle_refrigerated)
        return _dict(order_service.update_order(con, order_id, payload))

@mcp.tool
def delete_order(order_id: str) -> dict[str, Any]:
    with get_db() as con:
        return _dict(order_service.delete_order(con, order_id))

@mcp.tool
def list_plans() -> list[dict[str, Any]]:
    with get_db() as con:
        return [_dict(p) for p in plan_service.list_plans(con)]

@mcp.tool
def create_plan(plan_id: str, name: str) -> dict[str, Any]:
    with get_db() as con:
        payload = plan_schemas.PlanCreate(plan_id=plan_id, name=name)
        return _dict(plan_service.create_plan(con, payload))

@mcp.tool
def get_plan(plan_id: str) -> dict[str, Any]:
    with get_db() as con:
        return _dict(plan_service.get_plan(con, plan_id))

@mcp.tool
def add_order_to_plan(plan_id: str, order_id: str, driver_id: str, vehicle_id: str) -> dict[str, Any]:
    with get_db() as con:
        payload = plan_schemas.PlanOrderAdd(order_id=order_id, driver_id=driver_id, vehicle_id=vehicle_id)
        return _dict(plan_service.add_plan_order(con, plan_id, payload))

@mcp.tool
def generate_plan(plan_id: str) -> dict[str, Any]:
    with get_db() as con:
        return _dict(plan_service.generate_plan(con, plan_id))

@mcp.tool
def evaluate_plan(plan_id: str) -> dict[str, Any]:
    with get_db() as con:
        return _dict(plan_service.evaluate_plan(con, plan_id))

@mcp.tool
def run_matching() -> list[dict[str, Any]]:
    from core.config import DB_PATH
    results = matching_engine.run_corematch_logistics(DB_PATH)
    return [_dict(r) for r in results]

if __name__ == "__main__":
    mcp.run()

