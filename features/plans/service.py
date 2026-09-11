import duckdb
from typing import Sequence, Any
from core.database import query_models, execute_update, query_model_or_none, api_rows
from features.plans.schemas import Plan, PlanCreate, PlanOrderAssignment, PlanDetail, PlanEvaluation, StopEvaluation, RouteEvaluation, PlanOrderAdd, PlanRouteSwitch, PlanValidationResult
from datetime import datetime, timedelta
from core.config import DB_PATH
from features.matching.engine import run_corematch_logistics

def list_plans(con: duckdb.DuckDBPyConnection) -> Sequence[Plan]:
    return query_models(Plan, con, "SELECT plan_id, name FROM plans ORDER BY plan_id")

def create_plan(con: duckdb.DuckDBPyConnection, payload: PlanCreate) -> Plan:
    con.execute(
        "INSERT INTO plans (plan_id, name) VALUES (?, ?)",
        [payload.plan_id, payload.name],
    )
    plan = query_model_or_none(Plan, con, "SELECT plan_id, name FROM plans WHERE plan_id = ?", [payload.plan_id])
    if plan is None:
        raise ValueError("Failed to retrieve created plan")
    return plan

def get_plan(con: duckdb.DuckDBPyConnection, plan_id: str) -> PlanDetail | None:
    plan = query_model_or_none(Plan, con, "SELECT plan_id, name FROM plans WHERE plan_id = ?", [plan_id])
    if not plan:
        return None
    
    assignments = query_models(
        PlanOrderAssignment,
        con,
        "SELECT plan_id, order_id, driver_id, vehicle_id, stop_sequence FROM plan_orders WHERE plan_id = ? ORDER BY stop_sequence, order_id",
        [plan_id]
    )
    
    stops = query_models(
        StopEvaluation,
        con,
        "SELECT order_id, driver_id, vehicle_id, stop_sequence, origin_zip, destination_zip, driving_time_min, departure_time, arrival_time FROM plan_evaluations WHERE plan_id = ? ORDER BY stop_sequence, order_id",
        [plan_id]
    )
    
    routes = query_models(
        RouteEvaluation,
        con,
        "SELECT plan_id, driver_id, vehicle_id, start_zip, last_stop_zip, return_driving_time_min, return_departure_time, return_arrival_time FROM plan_route_evaluations WHERE plan_id = ?",
        [plan_id]
    )
    
    return PlanDetail(
        plan_id=plan.plan_id,
        name=plan.name,
        assignments=list(assignments),
        evaluation=PlanEvaluation(stops=list(stops), routes=list(routes))
    )

def add_plan_order(con: duckdb.DuckDBPyConnection, plan_id: str, payload: PlanOrderAdd) -> PlanDetail:
    if not api_rows(con, "SELECT 1 FROM plans WHERE plan_id = ?", [plan_id]):
        raise ValueError(f"Plan not found: {plan_id}")
    if not api_rows(con, "SELECT 1 FROM orders WHERE order_id = ?", [payload.order_id]):
        raise ValueError(f"Order not found: {payload.order_id}")
    if not api_rows(con, "SELECT 1 FROM drivers WHERE driver_id = ?", [payload.driver_id]):
        raise ValueError(f"Driver not found: {payload.driver_id}")
    if not api_rows(con, "SELECT 1 FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id]):
        raise ValueError(f"Vehicle not found: {payload.vehicle_id}")
    
    duplicate = api_rows(con, "SELECT 1 FROM plan_orders WHERE plan_id = ? AND order_id = ?", [plan_id, payload.order_id])
    if duplicate:
        raise ValueError("Order already in plan")
        
    con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
    con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
    
    max_seq_row = api_rows(
        con,
        "SELECT COALESCE(MAX(stop_sequence), 0) AS m FROM plan_orders WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?",
        [plan_id, payload.driver_id, payload.vehicle_id]
    )
    seq = max_seq_row[0]["m"] + 1
    
    con.execute(
        "INSERT INTO plan_orders (plan_id, order_id, driver_id, vehicle_id, stop_sequence) VALUES (?, ?, ?, ?, ?)",
        [plan_id, payload.order_id, payload.driver_id, payload.vehicle_id, seq]
    )
    detail = get_plan(con, plan_id)
    if detail is None:
        raise ValueError("Plan disappeared")
    return detail

def switch_plan_route(con: duckdb.DuckDBPyConnection, plan_id: str, current_driver_id: str, current_vehicle_id: str, payload: PlanRouteSwitch) -> PlanDetail:
    if not api_rows(con, "SELECT 1 FROM plan_orders WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?", [plan_id, current_driver_id, current_vehicle_id]):
        raise ValueError("Plan route not found")
    if not api_rows(con, "SELECT 1 FROM drivers WHERE driver_id = ?", [payload.driver_id]):
        raise ValueError(f"Driver not found: {payload.driver_id}")
    if not api_rows(con, "SELECT 1 FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id]):
        raise ValueError(f"Vehicle not found: {payload.vehicle_id}")
        
    con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
    con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
    
    con.execute(
        "UPDATE plan_orders SET driver_id = ?, vehicle_id = ? WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?",
        [payload.driver_id, payload.vehicle_id, plan_id, current_driver_id, current_vehicle_id]
    )
    
    detail = get_plan(con, plan_id)
    if detail is None:
        raise ValueError("Plan disappeared")
    return detail

def move_plan_order(con: duckdb.DuckDBPyConnection, plan_id: str, driver_id: str, vehicle_id: str, order_id: str, direction: int) -> PlanDetail:
    if direction not in (-1, 1):
        raise ValueError("Direction must be -1 or 1")
    
    route_orders = api_rows(
        con,
        "SELECT order_id, stop_sequence FROM plan_orders WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ? ORDER BY stop_sequence, order_id",
        [plan_id, driver_id, vehicle_id]
    )
    order_ids = [row["order_id"] for row in route_orders]
    if order_id not in order_ids:
        raise ValueError("Plan order not found")
        
    current_index = order_ids.index(order_id)
    neighbor_index = current_index + direction
    
    if neighbor_index < 0 or neighbor_index >= len(order_ids):
        raise ValueError("Cannot move order outside route bounds")
        
    neighbor_id = order_ids[neighbor_index]
    neighbor = next(row for row in route_orders if row["order_id"] == neighbor_id)
    current = next(row for row in route_orders if row["order_id"] == order_id)
    
    con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
    con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
    
    con.execute(
        "UPDATE plan_orders SET stop_sequence = ? WHERE plan_id = ? AND order_id = ?",
        [neighbor["stop_sequence"], plan_id, order_id]
    )
    con.execute(
        "UPDATE plan_orders SET stop_sequence = ? WHERE plan_id = ? AND order_id = ?",
        [current["stop_sequence"], plan_id, neighbor_id]
    )
    
    detail = get_plan(con, plan_id)
    if detail is None:
        raise ValueError("Plan disappeared")
    return detail

def generate_plan(con: duckdb.DuckDBPyConnection, plan_id: str) -> PlanDetail:
    plan = get_plan(con, plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")
        
    results = run_corematch_logistics(DB_PATH) # Separate connection internally
    matched = [r for r in results if r.status == "Fully Matched"]
    
    con.execute("DELETE FROM plan_orders WHERE plan_id = ?", [plan_id])
    
    assignments = [
        (plan_id, r.order_id, r.assigned_driver, r.assigned_vehicle, 1)
        for r in matched
    ]
    con.executemany(
        "INSERT INTO plan_orders (plan_id, order_id, driver_id, vehicle_id, stop_sequence) VALUES (?, ?, ?, ?, ?)",
        assignments
    )
    
    con.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
    con.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
    
    detail = get_plan(con, plan_id)
    if detail is None:
        raise ValueError("Plan disappeared")
    return detail

def evaluate_plan_routes_internal(rows: list[dict], travel_times: dict[tuple[str, str], int], start_hour: int = 9) -> dict[str, list[dict]]:
    route_clocks: dict[tuple[str, str], datetime] = {}
    route_locations: dict[tuple[str, str], str] = {}
    evaluated = []
    for row in rows:
        route = (row["driver_id"], row["vehicle_id"])
        departure = route_clocks.get(route, datetime(2000, 1, 1, start_hour))
        origin_zip = route_locations.get(route, row["start_zip"])
        driving_time = travel_times.get((origin_zip, row["destination_zip"]))
        if driving_time is None:
            raise ValueError(f"No distance matrix entry from {origin_zip} to {row['destination_zip']}")
        arrival = departure + timedelta(minutes=driving_time)
        evaluated.append({
            "order_id": row["order_id"],
            "driver_id": row["driver_id"],
            "vehicle_id": row["vehicle_id"],
            "stop_sequence": row["stop_sequence"],
            "origin_zip": origin_zip,
            "destination_zip": row["destination_zip"],
            "driving_time_min": driving_time,
            "departure_time": departure.strftime("%H:%M"),
            "arrival_time": arrival.strftime("%H:%M"),
        })
        route_clocks[route] = arrival
        route_locations[route] = row["destination_zip"]
        
    route_summaries = []
    for route, last_stop in route_locations.items():
        route_rows = [row for row in rows if (row["driver_id"], row["vehicle_id"]) == route]
        start_zip = route_rows[0]["start_zip"]
        departure = route_clocks[route]
        return_time = travel_times.get((last_stop, start_zip))
        if return_time is None:
            raise ValueError(f"No distance matrix entry from {last_stop} to {start_zip}")
        arrival = departure + timedelta(minutes=return_time)
        route_summaries.append({
            "plan_id": route_rows[0].get("plan_id"),
            "driver_id": route[0],
            "vehicle_id": route[1],
            "start_zip": start_zip,
            "last_stop_zip": last_stop,
            "return_driving_time_min": return_time,
            "return_departure_time": departure.strftime("%H:%M"),
            "return_arrival_time": arrival.strftime("%H:%M"),
        })
    return {"stops": evaluated, "routes": route_summaries}

def evaluate_plan(con: duckdb.DuckDBPyConnection, plan_id: str) -> PlanDetail:
    plan = get_plan(con, plan_id)
    if not plan:
        raise ValueError(f"Plan not found: {plan_id}")
        
    rows = api_rows(
        con,
        """
        SELECT po.plan_id, po.order_id, po.driver_id, po.vehicle_id, po.stop_sequence,
               o.destination_location_id, destination.zip AS destination_zip,
               start_location.zip AS start_zip
        FROM plan_orders po
        JOIN orders o ON o.order_id = po.order_id
        JOIN locations destination ON destination.location_id = o.destination_location_id
        JOIN drivers d ON d.driver_id = po.driver_id
        JOIN locations start_location ON start_location.location_id = d.location_id
        WHERE po.plan_id = ?
        ORDER BY po.driver_id, po.vehicle_id, po.stop_sequence, po.order_id
        """,
        [plan_id]
    )
    
    matrix = {(row["origin_zip"], row["dest_zip"]): row["travel_time_min"] for row in api_rows(con, "SELECT origin_zip, dest_zip, travel_time_min FROM distance_matrix")}
    
    evaluated = evaluate_plan_routes_internal(rows, matrix)
    
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
        [(plan_id, item["order_id"], item["driver_id"], item["vehicle_id"], item["stop_sequence"], item["origin_zip"], item["destination_zip"], item["driving_time_min"], item["departure_time"], item["arrival_time"]) for item in evaluated["stops"]]
    )
    
    con.executemany(
        """
        INSERT INTO plan_route_evaluations
            (plan_id, driver_id, vehicle_id, start_zip, last_stop_zip,
             return_driving_time_min, return_departure_time, return_arrival_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(plan_id, item["driver_id"], item["vehicle_id"], item["start_zip"], item["last_stop_zip"], item["return_driving_time_min"], item["return_departure_time"], item["return_arrival_time"]) for item in evaluated["routes"]]
    )
    
    detail = get_plan(con, plan_id)
    if detail is None:
        raise ValueError("Plan disappeared")
    return detail

def validate_plan(con: duckdb.DuckDBPyConnection, plan_id: str) -> PlanValidationResult:
    if not api_rows(con, "SELECT 1 FROM plans WHERE plan_id = ?", [plan_id]):
        raise ValueError(f"Plan not found: {plan_id}")
        
    errors = []
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
        LEFT JOIN locations driver_location ON driver_location.location_id = d.location_id
        LEFT JOIN locations vehicle_location ON vehicle_location.location_id = v.location_id
        WHERE po.plan_id = ?
        ORDER BY po.stop_sequence, po.order_id
        """,
        [plan_id]
    )
    
    for row in rows:
        r_str = f"assignment driver {row['driver_id']} vehicle {row['vehicle_id']} order {row['order_id']}"
        if not row["driver_active"]: errors.append(f"Inactive driver in {r_str}")
        if not row["vehicle_active"]: errors.append(f"Inactive vehicle in {r_str}")
        if row["req_driver_adr"] and not row["skill_adr"]: errors.append(f"Missing ADR skill in {r_str}")
        if row["req_driver_ehbo"] and not row["skill_ehbo"]: errors.append(f"Missing EHBO skill in {r_str}")
        if row["req_vehicle_liftgate"] and not row["spec_liftgate"]: errors.append(f"Missing Liftgate in {r_str}")
        if row["req_vehicle_refrigerated"] and not row["spec_refrigerated"]: errors.append(f"Missing Refrigerated spec in {r_str}")
        if row["driver_location_id"] != row["vehicle_location_id"]:
            matrix_check = api_rows(
                con,
                "SELECT travel_time_min FROM distance_matrix WHERE origin_zip = ? AND dest_zip = ?",
                [row["driver_zip"], row["vehicle_zip"]]
            )
            if not matrix_check or matrix_check[0]["travel_time_min"] > 30:
                errors.append(f"Distance > 30min between resources in {r_str}")
                
    return PlanValidationResult(errors=errors)

