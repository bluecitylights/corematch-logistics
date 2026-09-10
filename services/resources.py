"""Shared resource operations used by the REST and HTML interfaces."""

from typing import Any

from fastapi import HTTPException

from db import api_rows, api_update, get_db
from db.locations import rebuild_distance_matrix


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
