"""Shared resource operations used by the REST and HTML interfaces."""

from typing import Any
from fastapi import HTTPException

from db import api_rows, api_update, get_db
from db.locations import rebuild_distance_matrix
from engine import evaluate_plan_routes, run_corematch_logistics
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
        evaluation = api_rows(
            con,
            """
            SELECT plan_id, order_id, driver_id, vehicle_id, stop_sequence,
                   origin_zip, destination_zip, driving_time_min,
                   departure_time, arrival_time
            FROM plan_evaluations
            WHERE plan_id = ?
            ORDER BY stop_sequence, order_id
            """,
            [plan_id],
        )
        route_evaluation = api_rows(
            con,
            """
            SELECT plan_id, driver_id, vehicle_id, start_zip, last_stop_zip,
                   return_driving_time_min, return_departure_time,
                   return_arrival_time
            FROM plan_route_evaluations
            WHERE plan_id = ?
            ORDER BY driver_id, vehicle_id
            """,
            [plan_id],
        )
    evaluations_by_order = {
        item["order_id"]: item for item in evaluation
    }
    routes_by_key = {
        (item["driver_id"], item["vehicle_id"]): item
        for item in route_evaluation
    }
    route_groups = []
    for key, route_orders in _group_plan_orders_by_pair(assignments).items():
        driver_id, vehicle_id = key
        route_groups.append(
            {
                "driver_id": driver_id,
                "vehicle_id": vehicle_id,
                "stops": [
                    {
                        **order,
                        "evaluation": evaluations_by_order.get(order["order_id"]),
                    }
                    for order in route_orders
                ],
                "return": routes_by_key.get(key),
            }
        )
    return {
        **plans[0],
        "orders": assignments,
        "orders_by_driver": _group_plan_orders(assignments, "driver_id"),
        "orders_by_vehicle": _group_plan_orders(assignments, "vehicle_id"),
        "evaluation": evaluation,
        "route_evaluation": route_evaluation,
        "route_groups": route_groups,
    }


def validate_plan(plan_id: str) -> dict[str, Any]:
    """Validate plan assignments without changing plan or evaluation data."""
    errors: list[str] = []
    with get_db() as con:
        if not api_rows(con, "SELECT 1 FROM plans WHERE plan_id = ?", [plan_id]):
            raise HTTPException(404, f"Plan not found: {plan_id}")
        rows = api_rows(
            con,
            """
            SELECT po.order_id, po.driver_id, po.vehicle_id,
                   d.location_id AS driver_location_id,
                   d.is_active AS driver_active,
                   d.skill_adr, d.skill_ehbo,
                   v.location_id AS vehicle_location_id,
                   v.is_active AS vehicle_active,
                   v.spec_liftgate, v.spec_refrigerated,
                   o.req_driver_adr, o.req_driver_ehbo,
                   o.req_vehicle_liftgate, o.req_vehicle_refrigerated,
                   driver_location.zip AS driver_zip,
                   vehicle_location.zip AS vehicle_zip
            FROM plan_orders po
            LEFT JOIN drivers d ON d.driver_id = po.driver_id
            LEFT JOIN vehicles v ON v.vehicle_id = po.vehicle_id
            LEFT JOIN orders o ON o.order_id = po.order_id
            LEFT JOIN locations driver_location
              ON driver_location.location_id = d.location_id
            LEFT JOIN locations vehicle_location
              ON vehicle_location.location_id = v.location_id
            WHERE po.plan_id = ?
            ORDER BY po.stop_sequence, po.order_id
            """,
            [plan_id],
        )
        matrix = {
            (row["origin_zip"], row["dest_zip"]): row["travel_time_min"]
            for row in api_rows(
                con,
                "SELECT origin_zip, dest_zip, travel_time_min FROM distance_matrix",
            )
        }

    if not rows:
        errors.append("Plan has no orders.")

    driver_pairs: dict[str, set[str]] = {}
    vehicle_pairs: dict[str, set[str]] = {}
    for row in rows:
        order_id = row["order_id"]
        driver_id = row["driver_id"]
        vehicle_id = row["vehicle_id"]
        if not driver_id or not vehicle_id:
            errors.append(f"{order_id}: driver and vehicle are required.")
            continue
        driver_pairs.setdefault(driver_id, set()).add(vehicle_id)
        vehicle_pairs.setdefault(vehicle_id, set()).add(driver_id)
        if row["driver_active"] is not True:
            errors.append(f"{order_id}: driver {driver_id} is inactive or missing.")
        if row["vehicle_active"] is not True:
            errors.append(f"{order_id}: vehicle {vehicle_id} is inactive or missing.")
        if row["req_driver_adr"] and not row["skill_adr"]:
            errors.append(f"{order_id}: driver {driver_id} does not match ADR.")
        if row["req_driver_ehbo"] and not row["skill_ehbo"]:
            errors.append(f"{order_id}: driver {driver_id} does not match EHBO.")
        if row["req_vehicle_liftgate"] and not row["spec_liftgate"]:
            errors.append(f"{order_id}: vehicle {vehicle_id} does not match liftgate.")
        if row["req_vehicle_refrigerated"] and not row["spec_refrigerated"]:
            errors.append(
                f"{order_id}: vehicle {vehicle_id} does not match refrigerated."
            )
        travel_time = matrix.get((row["driver_zip"], row["vehicle_zip"]))
        if travel_time is None:
            errors.append(
                f"{order_id}: no distance matrix entry from driver {driver_id} "
                f"to vehicle {vehicle_id}."
            )
        elif travel_time > 30:
            errors.append(
                f"{order_id}: driver {driver_id} is {travel_time} minutes "
                f"from vehicle {vehicle_id}; maximum is 30."
            )

    for driver_id, vehicles in driver_pairs.items():
        if len(vehicles) > 1:
            errors.append(
                f"Driver {driver_id} is assigned to multiple vehicles: "
                f"{', '.join(sorted(vehicles))}."
            )
    for vehicle_id, drivers in vehicle_pairs.items():
        if len(drivers) > 1:
            errors.append(
                f"Vehicle {vehicle_id} is assigned to multiple drivers: "
                f"{', '.join(sorted(drivers))}."
            )
    return {"plan_id": plan_id, "valid": not errors, "errors": errors}


def _group_plan_orders(
    assignments: list[dict[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for assignment in assignments:
        resource_id = assignment[key]
        if resource_id is not None:
            grouped.setdefault(resource_id, []).append(assignment)
    return grouped


def _group_plan_orders_by_pair(
    assignments: list[dict[str, Any]],
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for assignment in assignments:
        key = (assignment["driver_id"], assignment["vehicle_id"])
        grouped.setdefault(key, []).append(assignment)
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
        if not api_rows(con, "SELECT 1 FROM drivers WHERE driver_id = ?", [driver_id]):
            raise HTTPException(404, f"Driver not found: {driver_id}")
        if not api_rows(con, "SELECT 1 FROM vehicles WHERE vehicle_id = ?", [vehicle_id]):
            raise HTTPException(404, f"Vehicle not found: {vehicle_id}")
        duplicate = api_rows(
            con,
            """
            SELECT 1
            FROM plan_orders
            WHERE plan_id = ? AND order_id = ?
            """,
            [plan_id, payload["order_id"]],
        )
        if duplicate:
            raise HTTPException(409, f"Order already exists in plan: {payload['order_id']}")
        next_sequence = con.execute(
            """
            SELECT COALESCE(MAX(stop_sequence), 0) + 1
            FROM plan_orders
            WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?
            """,
            [plan_id, driver_id, vehicle_id],
        ).fetchone()[0]
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
                payload.get("stop_sequence", next_sequence),
            ],
        )
        con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
        con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
    return get_plan(plan_id)


def switch_plan_route(
    plan_id: str,
    current_driver_id: str,
    current_vehicle_id: str,
    driver_id: str,
    vehicle_id: str,
) -> dict[str, Any]:
    with get_db() as con:
        route_exists = api_rows(
            con,
            """
            SELECT 1 FROM plan_orders
            WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?
            """,
            [plan_id, current_driver_id, current_vehicle_id],
        )
        if not route_exists:
            raise HTTPException(404, "Plan route not found")
        if not api_rows(con, "SELECT 1 FROM drivers WHERE driver_id = ?", [driver_id]):
            raise HTTPException(404, f"Driver not found: {driver_id}")
        if not api_rows(con, "SELECT 1 FROM vehicles WHERE vehicle_id = ?", [vehicle_id]):
            raise HTTPException(404, f"Vehicle not found: {vehicle_id}")
        con.execute(
            """
            UPDATE plan_orders
            SET driver_id = ?, vehicle_id = ?
            WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?
            """,
            [driver_id, vehicle_id, plan_id, current_driver_id, current_vehicle_id],
        )
        con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
        con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
    return get_plan(plan_id)


def move_plan_order(
    plan_id: str, driver_id: str, vehicle_id: str, order_id: str, direction: int
) -> dict[str, Any]:
    if direction not in (-1, 1):
        raise HTTPException(400, "Direction must be -1 or 1")
    with get_db() as con:
        route_orders = api_rows(
            con,
            """
            SELECT order_id, stop_sequence
            FROM plan_orders
            WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?
            ORDER BY stop_sequence, order_id
            """,
            [plan_id, driver_id, vehicle_id],
        )
        order_ids = [row["order_id"] for row in route_orders]
        if order_id not in order_ids:
            raise HTTPException(404, "Plan order not found")
        current_index = order_ids.index(order_id)
        neighbor_index = current_index + direction
        if 0 <= neighbor_index < len(order_ids):
            reordered = order_ids.copy()
            reordered[current_index], reordered[neighbor_index] = (
                reordered[neighbor_index],
                reordered[current_index],
            )
            con.execute(
                """
                UPDATE plan_orders
                SET stop_sequence = 1000000 + stop_sequence
                WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?
                """,
                [plan_id, driver_id, vehicle_id],
            )
            con.executemany(
                """
                UPDATE plan_orders
                SET stop_sequence = ?
                WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?
                  AND order_id = ?
                """,
                [
                    (sequence, plan_id, driver_id, vehicle_id, moved_order_id)
                    for sequence, moved_order_id in enumerate(reordered, start=1)
                ],
            )
        con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
        con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
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


def evaluate_plan(plan_id: str) -> dict[str, Any]:
    plan = get_plan(plan_id)
    with get_db() as con:
        rows = api_rows(
            con,
            """
            SELECT po.order_id, po.driver_id, po.vehicle_id, po.stop_sequence,
                   o.destination_location_id, destination.zip AS destination_zip,
                   start_location.zip AS start_zip
            FROM plan_orders po
            JOIN orders o ON o.order_id = po.order_id
            JOIN locations destination
              ON destination.location_id = o.destination_location_id
            JOIN drivers d ON d.driver_id = po.driver_id
            JOIN locations start_location
              ON start_location.location_id = d.location_id
            WHERE po.plan_id = ?
            ORDER BY po.driver_id, po.vehicle_id, po.stop_sequence, po.order_id
            """,
            [plan_id],
        )
        matrix = {
            (row["origin_zip"], row["dest_zip"]): row["travel_time_min"]
            for row in api_rows(
                con,
                "SELECT origin_zip, dest_zip, travel_time_min FROM distance_matrix",
            )
        }

    try:
        evaluated = evaluate_plan_routes(rows, matrix)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with get_db() as con:
        con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
        con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
        con.executemany(
            """
            INSERT INTO plan_evaluations
                (plan_id, order_id, driver_id, vehicle_id, stop_sequence,
                 origin_zip, destination_zip, driving_time_min,
                 departure_time, arrival_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    plan_id,
                    item["order_id"],
                    item["driver_id"],
                    item["vehicle_id"],
                    item["stop_sequence"],
                    item["origin_zip"],
                    item["destination_zip"],
                    item["driving_time_min"],
                    item["departure_time"],
                    item["arrival_time"],
                )
                for item in evaluated["stops"]
            ],
        )
        con.executemany(
            """
            INSERT INTO plan_route_evaluations
                (plan_id, driver_id, vehicle_id, start_zip, last_stop_zip,
                 return_driving_time_min, return_departure_time,
                 return_arrival_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    plan_id,
                    item["driver_id"],
                    item["vehicle_id"],
                    item["start_zip"],
                    item["last_stop_zip"],
                    item["return_driving_time_min"],
                    item["return_departure_time"],
                    item["return_arrival_time"],
                )
                for item in evaluated["routes"]
            ],
        )
    return get_plan(plan_id)
