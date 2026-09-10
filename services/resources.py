"""Shared resource operations used by the REST and HTML interfaces."""

from typing import Any

from fastapi import HTTPException

from db import api_rows, api_update, get_db
from db.locations import rebuild_distance_matrix
from engine import run_corematch_logistics
from db import DB_PATH


def list_resources(table: str, include_inactive: bool = False) -> list[dict[str, Any]]:
    where = "" if include_inactive else "WHERE is_active"
    with get_db() as con:
        return api_rows(con, f"SELECT * FROM {table} {where} ORDER BY " + (
            "driver_index" if table == "drivers" else "vehicle_index"
        ))


def create_driver(payload: dict[str, Any]) -> dict[str, Any]:
    with get_db() as con:
        con.execute(
            "INSERT INTO drivers (driver_id, location_id, skill_adr, skill_ehbo) VALUES (?, ?, ?, ?)",
            [payload["driver_id"], payload["location_id"], payload.get("skill_adr", False), payload.get("skill_ehbo", False)],
        )
        return api_rows(con, "SELECT * FROM drivers WHERE driver_id = ?", [payload["driver_id"]])[0]


def update_driver(driver_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    return api_update("drivers", "driver_id", driver_id, fields)


def create_vehicle(payload: dict[str, Any]) -> dict[str, Any]:
    with get_db() as con:
        con.execute(
            "INSERT INTO vehicles (vehicle_id, license_plate, location_id, spec_liftgate, spec_refrigerated) VALUES (?, ?, ?, ?, ?)",
            [payload["vehicle_id"], payload["license_plate"], payload["location_id"], payload.get("spec_liftgate", False), payload.get("spec_refrigerated", False)],
        )
        return api_rows(con, "SELECT * FROM vehicles WHERE vehicle_id = ?", [payload["vehicle_id"]])[0]


def update_vehicle(vehicle_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    return api_update("vehicles", "vehicle_id", vehicle_id, fields)


def list_orders() -> list[dict[str, Any]]:
    with get_db() as con:
        return api_rows(con, "SELECT * FROM orders ORDER BY order_id")


def list_locations() -> list[dict[str, Any]]:
    with get_db() as con:
        return api_rows(con, "SELECT * FROM locations ORDER BY zip")


def create_location(payload: dict[str, Any]) -> dict[str, Any]:
    with get_db() as con:
        con.execute(
            "INSERT INTO locations (zip, city, latitude, longitude) VALUES (?, ?, ?, ?)",
            [payload["zip"], payload["city"], payload["latitude"], payload["longitude"]],
        )
        rebuild_distance_matrix(con)
        return api_rows(
            con,
            "SELECT * FROM locations WHERE zip = ?",
            [payload["zip"]],
        )[0]


def create_order(payload: dict[str, Any]) -> dict[str, Any]:
    columns = ("order_id", "destination_location_id", "req_driver_adr", "req_driver_ehbo", "req_vehicle_liftgate", "req_vehicle_refrigerated")
    with get_db() as con:
        con.execute(
            f"INSERT INTO orders ({', '.join(columns)}) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.get(column, False) if column not in ("order_id", "destination_location_id") else payload[column] for column in columns],
        )
        return api_rows(con, "SELECT * FROM orders WHERE order_id = ?", [payload["order_id"]])[0]


def update_order(order_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    return api_update("orders", "order_id", order_id, fields)


def delete_order(order_id: str) -> dict[str, Any]:
    with get_db() as con:
        rows = api_rows(con, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        if not rows:
            raise HTTPException(404, f"Order not found: {order_id}")
        con.execute("DELETE FROM orders WHERE order_id = ?", [order_id])
        return rows[0]


def list_plans() -> list[dict[str, Any]]:
    with get_db() as con:
        return api_rows(con, "SELECT plan_id, name FROM plans ORDER BY plan_id")


def create_plan(payload: dict[str, Any]) -> dict[str, Any]:
    with get_db() as con:
        con.execute(
            "INSERT INTO plans (plan_id, name) VALUES (?, ?)",
            [payload["plan_id"], payload["name"]],
        )
        return api_rows(
            con,
            "SELECT plan_id, name FROM plans WHERE plan_id = ?",
            [payload["plan_id"]],
        )[0]


def get_plan(plan_id: str) -> dict[str, Any]:
    with get_db() as con:
        plans = api_rows(
            con, "SELECT plan_id, name FROM plans WHERE plan_id = ?", [plan_id]
        )
        if not plans:
            raise HTTPException(404, f"Plan not found: {plan_id}")
        assignments = api_rows(
            con,
            """
            SELECT plan_id, order_id, driver_id, vehicle_id, stop_sequence
            FROM plan_orders
            WHERE plan_id = ?
            ORDER BY stop_sequence, order_id
            """,
            [plan_id],
        )
    return {
        **plans[0],
        "orders": assignments,
        "orders_by_driver": _group_plan_orders(assignments, "driver_id"),
        "orders_by_vehicle": _group_plan_orders(assignments, "vehicle_id"),
    }


def _group_plan_orders(
    assignments: list[dict[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for assignment in assignments:
        resource_id = assignment[key]
        if resource_id is not None:
            grouped.setdefault(resource_id, []).append(assignment)
    return grouped


def add_plan_order(plan_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    driver_id = payload.get("driver_id")
    vehicle_id = payload.get("vehicle_id")
    if not driver_id or not vehicle_id:
        raise HTTPException(
            400,
            "driver_id and vehicle_id are required; a plan uses one driver-vehicle combination",
        )
    with get_db() as con:
        if not api_rows(con, "SELECT 1 FROM plans WHERE plan_id = ?", [plan_id]):
            raise HTTPException(404, f"Plan not found: {plan_id}")
        if not api_rows(con, "SELECT 1 FROM orders WHERE order_id = ?", [payload["order_id"]]):
            raise HTTPException(404, f"Order not found: {payload['order_id']}")
        existing = api_rows(
            con,
            """
            SELECT DISTINCT driver_id, vehicle_id
            FROM plan_orders
            WHERE plan_id = ?
            """,
            [plan_id],
        )
        if existing and any(
            assignment["driver_id"] != driver_id
            or assignment["vehicle_id"] != vehicle_id
            for assignment in existing
        ):
            raise HTTPException(
                409,
                f"Plan {plan_id} already uses a different driver-vehicle combination",
            )
        con.execute(
            """
            INSERT INTO plan_orders
                (plan_id, order_id, driver_id, vehicle_id, stop_sequence)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                plan_id,
                payload["order_id"],
                driver_id,
                vehicle_id,
                payload.get("stop_sequence", 0),
            ],
        )
    return get_plan(plan_id)


def generate_plan(plan_id: str) -> dict[str, Any]:
    plan = get_plan(plan_id)
    results = run_corematch_logistics(DB_PATH).to_dict(orient="records")
    matched = [
        result for result in results
        if result["status"] == "Fully Matched"
    ]
    with get_db() as con:
        con.execute("DELETE FROM plan_orders WHERE plan_id = ?", [plan_id])
        con.executemany(
            """
            INSERT INTO plan_orders
                (plan_id, order_id, driver_id, vehicle_id, stop_sequence)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    plan_id,
                    result["order_id"],
                    result["assigned_driver"],
                    result["assigned_vehicle"],
                    sequence,
                )
                for sequence, result in enumerate(matched, start=1)
            ],
        )
    return get_plan(plan["plan_id"])
