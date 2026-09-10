"""REST API routes for CoreMatch resources."""

import json

from fastapi import APIRouter, Body, HTTPException

from db import DB_PATH, api_rows, api_update, get_db
from engine import run_corematch_logistics


router = APIRouter(prefix="/api")


@router.get("/drivers")
async def api_drivers(include_inactive: bool = False):
    with get_db() as con:
        where = "" if include_inactive else "WHERE is_active"
        return api_rows(con, f"SELECT * FROM drivers {where} ORDER BY driver_index")


@router.post("/drivers")
async def api_create_driver(payload: dict = Body(...)):
    required = ("driver_id", "location")
    if any(field not in payload for field in required):
        raise HTTPException(400, "driver_id and location are required")
    with get_db() as con:
        con.execute(
            "INSERT INTO drivers (driver_id, location, skill_adr, skill_ehbo) VALUES (?, ?, ?, ?)",
            [payload["driver_id"], payload["location"], payload.get("skill_adr", False), payload.get("skill_ehbo", False)],
        )
        return api_rows(con, "SELECT * FROM drivers WHERE driver_id = ?", [payload["driver_id"]])[0]


@router.patch("/drivers/{driver_id}")
async def api_update_driver(driver_id: str, payload: dict = Body(...)):
    allowed = {"location", "is_active", "skill_adr", "skill_ehbo"}
    fields = {key: value for key, value in payload.items() if key in allowed}
    return api_update("drivers", "driver_id", driver_id, fields)


@router.delete("/drivers/{driver_id}")
async def api_delete_driver(driver_id: str):
    return await api_update_driver(driver_id, {"is_active": False})


@router.get("/vehicles")
async def api_vehicles(include_inactive: bool = False):
    with get_db() as con:
        where = "" if include_inactive else "WHERE is_active"
        return api_rows(con, f"SELECT * FROM vehicles {where} ORDER BY vehicle_index")


@router.post("/vehicles")
async def api_create_vehicle(payload: dict = Body(...)):
    required = ("vehicle_id", "license_plate", "location")
    if any(field not in payload for field in required):
        raise HTTPException(400, "vehicle_id, license_plate, and location are required")
    with get_db() as con:
        con.execute(
            "INSERT INTO vehicles (vehicle_id, license_plate, location, spec_liftgate, spec_refrigerated) VALUES (?, ?, ?, ?, ?)",
            [payload["vehicle_id"], payload["license_plate"], payload["location"], payload.get("spec_liftgate", False), payload.get("spec_refrigerated", False)],
        )
        return api_rows(con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [payload["vehicle_id"]])[0]


@router.patch("/vehicles/{vehicle_id}")
async def api_update_vehicle(vehicle_id: str, payload: dict = Body(...)):
    allowed = {"license_plate", "location", "is_active", "spec_liftgate", "spec_refrigerated"}
    fields = {key: value for key, value in payload.items() if key in allowed}
    return api_update("vehicles", "vehicle_id", vehicle_id, fields)


@router.delete("/vehicles/{vehicle_id}")
async def api_delete_vehicle(vehicle_id: str):
    return await api_update_vehicle(vehicle_id, {"is_active": False})


@router.get("/orders")
async def api_orders():
    with get_db() as con:
        return api_rows(con, "SELECT * FROM orders ORDER BY order_id")


@router.post("/orders")
async def api_create_order(payload: dict = Body(...)):
    required = ("order_id", "destination")
    if any(field not in payload for field in required):
        raise HTTPException(400, "order_id and destination are required")
    columns = ("order_id", "destination", "req_driver_adr", "req_driver_ehbo", "req_vehicle_liftgate", "req_vehicle_refrigerated")
    with get_db() as con:
        con.execute(
            f"INSERT INTO orders ({', '.join(columns)}) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.get(column, False) if column not in ("order_id", "destination") else payload[column] for column in columns],
        )
        return api_rows(con, "SELECT * FROM orders WHERE order_id = ?", [payload["order_id"]])[0]


@router.patch("/orders/{order_id}")
async def api_update_order(order_id: str, payload: dict = Body(...)):
    allowed = {"destination", "req_driver_adr", "req_driver_ehbo", "req_vehicle_liftgate", "req_vehicle_refrigerated"}
    fields = {key: value for key, value in payload.items() if key in allowed}
    return api_update("orders", "order_id", order_id, fields)


@router.delete("/orders/{order_id}")
async def api_delete_order(order_id: str):
    with get_db() as con:
        rows = api_rows(con, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        if not rows:
            raise HTTPException(404, f"Order not found: {order_id}")
        con.execute("DELETE FROM orders WHERE order_id = ?", [order_id])
        return rows[0]


@router.post("/match")
async def api_match():
    results = run_corematch_logistics(DB_PATH)
    return json.loads(results.to_json(orient="records"))
