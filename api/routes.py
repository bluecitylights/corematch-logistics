"""REST API routes for CoreMatch resources."""

import json

from fastapi import APIRouter, Body, HTTPException

from db import DB_PATH, api_rows, api_update, get_db
from engine import run_corematch_logistics
from services.resources import (
    create_driver,
    create_order,
    create_location,
    create_vehicle,
    create_plan,
    add_plan_order,
    delete_order,
    list_orders,
    list_locations,
    list_plans,
    get_plan,
    generate_plan,
    evaluate_plan,
    validate_plan,
    switch_plan_route,
    move_plan_order,
    list_resources,
    update_driver,
    update_order,
    update_vehicle,
)


router = APIRouter(prefix="/api")


@router.get("/drivers")
async def api_drivers(include_inactive: bool = False):
    return list_resources("drivers", include_inactive)


@router.post("/drivers")
async def api_create_driver(payload: dict = Body(...)):
    required = ("driver_id", "location_id")
    if any(field not in payload for field in required):
        raise HTTPException(400, "driver_id and location_id are required")
    return create_driver(payload)


@router.patch("/drivers/{driver_id}")
async def api_update_driver(driver_id: str, payload: dict = Body(...)):
    allowed = {"location_id", "is_active", "skill_adr", "skill_ehbo"}
    fields = {key: value for key, value in payload.items() if key in allowed}
    return update_driver(driver_id, fields)


@router.delete("/drivers/{driver_id}")
async def api_delete_driver(driver_id: str):
    return await api_update_driver(driver_id, {"is_active": False})


@router.get("/vehicles")
async def api_vehicles(include_inactive: bool = False):
    return list_resources("vehicles", include_inactive)


@router.post("/vehicles")
async def api_create_vehicle(payload: dict = Body(...)):
    required = ("vehicle_id", "license_plate", "location_id")
    if any(field not in payload for field in required):
        raise HTTPException(400, "vehicle_id, license_plate, and location_id are required")
    return create_vehicle(payload)


@router.patch("/vehicles/{vehicle_id}")
async def api_update_vehicle(vehicle_id: str, payload: dict = Body(...)):
    allowed = {"license_plate", "location_id", "is_active", "spec_liftgate", "spec_refrigerated"}
    fields = {key: value for key, value in payload.items() if key in allowed}
    return update_vehicle(vehicle_id, fields)


@router.delete("/vehicles/{vehicle_id}")
async def api_delete_vehicle(vehicle_id: str):
    return await api_update_vehicle(vehicle_id, {"is_active": False})


@router.get("/orders")
async def api_orders():
    return list_orders()


@router.get("/locations")
async def api_locations():
    return list_locations()


@router.post("/locations")
async def api_create_location(payload: dict = Body(...)):
    required = ("zip", "city", "latitude", "longitude")
    if any(field not in payload for field in required):
        raise HTTPException(400, "zip, city, latitude, and longitude are required")
    return create_location(payload)


@router.get("/distance-matrix/{origin_zip}")
async def api_distance_matrix(origin_zip: str):
    with get_db() as con:
        rows = api_rows(
            con,
            """
            SELECT dest_zip, distance_m, travel_time_min
            FROM distance_matrix
            WHERE origin_zip = ?
            ORDER BY travel_time_min, dest_zip
            """,
            [origin_zip],
        )
        if not rows:
            raise HTTPException(404, f"Location not found: {origin_zip}")
        return rows


@router.post("/orders")
async def api_create_order(payload: dict = Body(...)):
    required = ("order_id", "destination_location_id")
    if any(field not in payload for field in required):
        raise HTTPException(400, "order_id and destination_location_id are required")
    return create_order(payload)


@router.get("/plans")
async def api_plans():
    return list_plans()


@router.post("/plans")
async def api_create_plan(payload: dict = Body(...)):
    required = ("plan_id", "name")
    if any(field not in payload for field in required):
        raise HTTPException(400, "plan_id and name are required")
    return create_plan(payload)


@router.get("/plans/{plan_id}")
async def api_plan(plan_id: str):
    return get_plan(plan_id)


@router.post("/plans/{plan_id}/orders")
async def api_add_plan_order(plan_id: str, payload: dict = Body(...)):
    if "order_id" not in payload:
        raise HTTPException(400, "order_id is required")
    return add_plan_order(plan_id, payload)


@router.post("/plans/{plan_id}/match")
async def api_generate_plan(plan_id: str):
    return generate_plan(plan_id)


@router.post("/plans/{plan_id}/evaluate")
async def api_evaluate_plan(plan_id: str):
    return evaluate_plan(plan_id)


@router.post("/plans/{plan_id}/validate")
async def api_validate_plan(plan_id: str):
    return validate_plan(plan_id)


@router.patch("/plans/{plan_id}/routes")
async def api_switch_plan_route(plan_id: str, payload: dict = Body(...)):
    required = ("current_driver_id", "current_vehicle_id", "driver_id", "vehicle_id")
    if any(field not in payload for field in required):
        raise HTTPException(400, "Current and replacement driver/vehicle are required")
    return switch_plan_route(plan_id, **{field: payload[field] for field in required})


@router.post("/plans/{plan_id}/orders/{order_id}/move")
async def api_move_plan_order(plan_id: str, order_id: str, payload: dict = Body(...)):
    return move_plan_order(
        plan_id,
        payload.get("driver_id"),
        payload.get("vehicle_id"),
        order_id,
        payload.get("direction"),
    )


@router.patch("/orders/{order_id}")
async def api_update_order(order_id: str, payload: dict = Body(...)):
    allowed = {"destination_location_id", "req_driver_adr", "req_driver_ehbo", "req_vehicle_liftgate", "req_vehicle_refrigerated"}
    fields = {key: value for key, value in payload.items() if key in allowed}
    return update_order(order_id, fields)


@router.delete("/orders/{order_id}")
async def api_delete_order(order_id: str):
    return delete_order(order_id)


@router.post("/match")
async def api_match():
    results = run_corematch_logistics(DB_PATH)
    return json.loads(results.to_json(orient="records"))
