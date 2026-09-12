import duckdb
from typing import Sequence, Any
from core.base_service import BaseService
from core.database import query_models, execute_update, query_model_or_none, api_rows
from features.plans.schemas import Plan, PlanCreate, PlanOrderAssignment, PlanDetail, PlanEvaluation, StopEvaluation, RouteEvaluation, PlanOrderAdd, PlanRouteSwitch, PlanValidationResult
from datetime import datetime, timedelta
from core.config import DB_PATH
from features.matching.engine import run_corematch_logistics


class PlanService(BaseService):
    """Domain service for managing delivery plans, routes, evaluations, and validations."""

    def list_plans(self, con: duckdb.DuckDBPyConnection | None = None) -> Sequence[Plan]:
        with self._get_con(con) as c:
            return query_models(Plan, c, "SELECT plan_id, name FROM plans ORDER BY plan_id")

    def create_plan(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Plan:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            payload = arg2
        else:
            payload = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            c.execute(
                "INSERT INTO plans (plan_id, name) VALUES (?, ?)",
                [payload.plan_id, payload.name],
            )
            plan = query_model_or_none(Plan, c, "SELECT plan_id, name FROM plans WHERE plan_id = ?", [payload.plan_id])
            if plan is None:
                raise ValueError("Failed to retrieve created plan")
            return plan

    def get_plan(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> PlanDetail | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            plan_id = arg2
        else:
            plan_id = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            plan = query_model_or_none(Plan, c, "SELECT plan_id, name FROM plans WHERE plan_id = ?", [plan_id])
            if not plan:
                return None
            
            assignments = query_models(
                PlanOrderAssignment,
                c,
                "SELECT plan_id, order_id, driver_id, vehicle_id, stop_sequence FROM plan_orders WHERE plan_id = ? ORDER BY stop_sequence, order_id",
                [plan_id]
            )
            
            stops = query_models(
                StopEvaluation,
                c,
                "SELECT order_id, driver_id, vehicle_id, stop_sequence, origin_zip, destination_zip, driving_time_min, departure_time, arrival_time FROM plan_evaluations WHERE plan_id = ? ORDER BY stop_sequence, order_id",
                [plan_id]
            )
            
            routes = query_models(
                RouteEvaluation,
                c,
                "SELECT plan_id, driver_id, vehicle_id, start_zip, last_stop_zip, return_driving_time_min, return_departure_time, return_arrival_time FROM plan_route_evaluations WHERE plan_id = ?",
                [plan_id]
            )
            
            return PlanDetail(
                plan_id=plan.plan_id,
                name=plan.name,
                assignments=list(assignments),
                evaluation=PlanEvaluation(stops=list(stops), routes=list(routes))
            )

    def add_plan_order(self, arg1: Any, arg2: Any, arg3: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> PlanDetail:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            plan_id = arg2
            payload = arg3
        else:
            plan_id = arg1
            payload = arg2
            c_passed = con or (arg3 if isinstance(arg3, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            if not api_rows(c, "SELECT 1 FROM plans WHERE plan_id = ?", [plan_id]):
                raise ValueError(f"Plan not found: {plan_id}")
            if not api_rows(c, "SELECT 1 FROM orders WHERE order_id = ?", [payload.order_id]):
                raise ValueError(f"Order not found: {payload.order_id}")
            if not api_rows(c, "SELECT 1 FROM drivers WHERE driver_id = ?", [payload.driver_id]):
                raise ValueError(f"Driver not found: {payload.driver_id}")
            if not api_rows(c, "SELECT 1 FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id]):
                raise ValueError(f"Vehicle not found: {payload.vehicle_id}")
            
            duplicate = api_rows(c, "SELECT 1 FROM plan_orders WHERE plan_id = ? AND order_id = ?", [plan_id, payload.order_id])
            if duplicate:
                raise ValueError("Order already in plan")
                
            c.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
            c.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
            
            max_seq_row = api_rows(
                c,
                "SELECT COALESCE(MAX(stop_sequence), 0) AS m FROM plan_orders WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?",
                [plan_id, payload.driver_id, payload.vehicle_id]
            )
            seq = max_seq_row[0]["m"] + 1
            
            c.execute(
                "INSERT INTO plan_orders (plan_id, order_id, driver_id, vehicle_id, stop_sequence) VALUES (?, ?, ?, ?, ?)",
                [plan_id, payload.order_id, payload.driver_id, payload.vehicle_id, seq]
            )
            detail = self.get_plan(plan_id, con=c)
            if detail is None:
                raise ValueError("Plan disappeared")
            return detail

    def switch_plan_route(self, *args, con: duckdb.DuckDBPyConnection | None = None, **kwargs) -> PlanDetail:
        if args and isinstance(args[0], duckdb.DuckDBPyConnection):
            c_passed = args[0]
            plan_id, current_driver_id, current_vehicle_id, payload = args[1:5]
        else:
            plan_id, current_driver_id, current_vehicle_id, payload = args[0:4]
            c_passed = con
        with self._get_con(c_passed) as c:
            if not api_rows(c, "SELECT 1 FROM plan_orders WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?", [plan_id, current_driver_id, current_vehicle_id]):
                raise ValueError("Plan route not found")
            if not api_rows(c, "SELECT 1 FROM drivers WHERE driver_id = ?", [payload.driver_id]):
                raise ValueError(f"Driver not found: {payload.driver_id}")
            if not api_rows(c, "SELECT 1 FROM vehicles WHERE vehicle_id = ?", [payload.vehicle_id]):
                raise ValueError(f"Vehicle not found: {payload.vehicle_id}")
                
            c.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
            c.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
            
            c.execute(
                "UPDATE plan_orders SET driver_id = ?, vehicle_id = ? WHERE plan_id = ? AND driver_id = ? AND vehicle_id = ?",
                [payload.driver_id, payload.vehicle_id, plan_id, current_driver_id, current_vehicle_id]
            )
            
            detail = self.get_plan(plan_id, con=c)
            if detail is None:
                raise ValueError("Plan disappeared")
            return detail

    def move_plan_order(self, *args, direction: int | None = None, con: duckdb.DuckDBPyConnection | None = None, **kwargs) -> PlanDetail:
        if args and isinstance(args[0], duckdb.DuckDBPyConnection):
            c_passed = args[0]
            plan_id, driver_id, vehicle_id, order_id = args[1:5]
            direction = direction if direction is not None else (args[5] if len(args) > 5 else kwargs.get("direction"))
        else:
            plan_id, driver_id, vehicle_id, order_id = args[0:4]
            direction = direction if direction is not None else (args[4] if len(args) > 4 else kwargs.get("direction"))
            c_passed = con
            
        if direction not in (-1, 1):
            raise ValueError("Direction must be -1 or 1")
        
        with self._get_con(c_passed) as c:
            route_orders = api_rows(
                c,
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
            
            c.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
            c.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
            
            c.execute(
                "UPDATE plan_orders SET stop_sequence = ? WHERE plan_id = ? AND order_id = ?",
                [neighbor["stop_sequence"], plan_id, order_id]
            )
            c.execute(
                "UPDATE plan_orders SET stop_sequence = ? WHERE plan_id = ? AND order_id = ?",
                [current["stop_sequence"], plan_id, neighbor_id]
            )
            
            detail = self.get_plan(plan_id, con=c)
            if detail is None:
                raise ValueError("Plan disappeared")
            return detail

    def generate_plan(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> PlanDetail:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            plan_id = arg2
        else:
            plan_id = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            plan = self.get_plan(plan_id, con=c)
            if not plan:
                raise ValueError(f"Plan not found: {plan_id}")
                
            results = run_corematch_logistics(c)
            matched = [r for r in results if r.status == "Fully Matched"]

            
            c.execute("DELETE FROM plan_orders WHERE plan_id = ?", [plan_id])
            
            assignments = [
                (plan_id, r.order_id, r.assigned_driver, r.assigned_vehicle, 1)
                for r in matched
            ]
            if assignments:
                c.executemany(
                    "INSERT INTO plan_orders (plan_id, order_id, driver_id, vehicle_id, stop_sequence) VALUES (?, ?, ?, ?, ?)",
                    assignments
                )
            
            c.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
            c.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
            
            detail = self.get_plan(plan_id, con=c)
            if detail is None:
                raise ValueError("Plan disappeared")
            return detail

    def evaluate_plan(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> PlanDetail:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            plan_id = arg2
        else:
            plan_id = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            plan = self.get_plan(plan_id, con=c)
            if not plan:
                raise ValueError(f"Plan not found: {plan_id}")
                
            rows = api_rows(
                c,
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
            
            matrix = {(row["origin_zip"], row["dest_zip"]): row["travel_time_min"] for row in api_rows(c, "SELECT origin_zip, dest_zip, travel_time_min FROM distance_matrix")}
            
            evaluated = evaluate_plan_routes_internal(rows, matrix)
            
            c.execute("DELETE FROM plan_evaluations WHERE plan_id = ?", [plan_id])
            c.execute("DELETE FROM plan_route_evaluations WHERE plan_id = ?", [plan_id])
            
            if evaluated["stops"]:
                c.executemany(
                    """
                    INSERT INTO plan_evaluations
                        (plan_id, order_id, driver_id, vehicle_id, stop_sequence,
                         origin_zip, destination_zip, driving_time_min,
                         departure_time, arrival_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [(plan_id, item["order_id"], item["driver_id"], item["vehicle_id"], item["stop_sequence"], item["origin_zip"], item["destination_zip"], item["driving_time_min"], item["departure_time"], item["arrival_time"]) for item in evaluated["stops"]]
                )
            
            if evaluated["routes"]:
                c.executemany(
                    """
                    INSERT INTO plan_route_evaluations
                        (plan_id, driver_id, vehicle_id, start_zip, last_stop_zip,
                         return_driving_time_min, return_departure_time, return_arrival_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [(plan_id, item["driver_id"], item["vehicle_id"], item["start_zip"], item["last_stop_zip"], item["return_driving_time_min"], item["return_departure_time"], item["return_arrival_time"]) for item in evaluated["routes"]]
                )
            
            detail = self.get_plan(plan_id, con=c)
            if detail is None:
                raise ValueError("Plan disappeared")
            return detail

    def validate_plan(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> PlanValidationResult:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            plan_id = arg2
        else:
            plan_id = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            if not api_rows(c, "SELECT 1 FROM plans WHERE plan_id = ?", [plan_id]):
                raise ValueError(f"Plan not found: {plan_id}")
                
            errors = []
            rows = api_rows(
                c,
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
                        c,
                        "SELECT travel_time_min FROM distance_matrix WHERE origin_zip = ? AND dest_zip = ?",
                        [row["driver_zip"], row["vehicle_zip"]]
                    )
                    if not matrix_check or matrix_check[0]["travel_time_min"] > 30:
                        errors.append(f"Distance > 30min between resources in {r_str}")
                        
            return PlanValidationResult(errors=errors)


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


def get_plan_service():
    with get_db() as con:
        yield PlanService(con)


plan_service = PlanService()

# Backward-compatibility aliases
list_plans = plan_service.list_plans
create_plan = plan_service.create_plan
get_plan = plan_service.get_plan
add_plan_order = plan_service.add_plan_order
switch_plan_route = plan_service.switch_plan_route
move_plan_order = plan_service.move_plan_order
generate_plan = plan_service.generate_plan
evaluate_plan = plan_service.evaluate_plan
validate_plan = plan_service.validate_plan


