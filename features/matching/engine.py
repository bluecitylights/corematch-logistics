import duckdb
import pandas as pd
from pyroaring import BitMap
from typing import Sequence
from features.matching.schemas import MatchResult


def _execute_matching(con: duckdb.DuckDBPyConnection) -> Sequence[MatchResult]:
    """Execute dual-resource matching against a live DuckDB connection or cursor."""
    drivers_df = con.execute("SELECT * FROM drivers").fetchdf()
    vehicles_df = con.execute("SELECT * FROM vehicles").fetchdf()
    orders_df = con.execute("SELECT * FROM orders").fetchdf()

    if orders_df.empty:
        return []

    resource_locations_query = """
        SELECT d.driver_index, v.vehicle_index 
        FROM distance_matrix dm
        JOIN drivers d ON dm.origin_zip = (SELECT zip FROM locations WHERE location_id = d.location_id)
        JOIN vehicles v ON dm.dest_zip = (SELECT zip FROM locations WHERE location_id = v.location_id)
        WHERE dm.travel_time_min <= 30
    """

    try:
        if drivers_df.empty or vehicles_df.empty:
            allowed_pairs = []
        else:
            allowed_pairs = con.execute(resource_locations_query).fetchall()
    except duckdb.Error:
        allowed_pairs = []

    # Format distance allowances
    allowed_drivers_by_vehicle: dict[int, BitMap] = {}
    allowed_vehicles_by_driver: dict[int, BitMap] = {}
    for d_idx, v_idx in allowed_pairs:
        if d_idx not in allowed_vehicles_by_driver:
            allowed_vehicles_by_driver[d_idx] = BitMap()
        allowed_vehicles_by_driver[d_idx].add(v_idx)

        if v_idx not in allowed_drivers_by_vehicle:
            allowed_drivers_by_vehicle[v_idx] = BitMap()
        allowed_drivers_by_vehicle[v_idx].add(d_idx)

    # Build BitMap indexes
    active_drivers = BitMap(drivers_df.loc[drivers_df["is_active"] == True, "driver_index"].tolist()) if not drivers_df.empty else BitMap()
    active_vehicles = BitMap(vehicles_df.loc[vehicles_df["is_active"] == True, "vehicle_index"].tolist()) if not vehicles_df.empty else BitMap()

    driver_features = {
        "adr": BitMap(drivers_df.loc[drivers_df["skill_adr"] == True, "driver_index"].tolist()) if not drivers_df.empty else BitMap(),
        "ehbo": BitMap(drivers_df.loc[drivers_df["skill_ehbo"] == True, "driver_index"].tolist()) if not drivers_df.empty else BitMap(),
    }

    vehicle_features = {
        "liftgate": BitMap(vehicles_df.loc[vehicles_df["spec_liftgate"] == True, "vehicle_index"].tolist()) if not vehicles_df.empty else BitMap(),
        "refrigerated": BitMap(vehicles_df.loc[vehicles_df["spec_refrigerated"] == True, "vehicle_index"].tolist()) if not vehicles_df.empty else BitMap(),
    }

    # Matching loop
    assigned_drivers: BitMap = BitMap()
    assigned_vehicles: BitMap = BitMap()
    results: list[MatchResult] = []

    for _, order in orders_df.iterrows():
        driver_pool = active_drivers.copy()
        if order.get("req_driver_adr") is True:
            driver_pool &= driver_features["adr"]
        if order.get("req_driver_ehbo") is True:
            driver_pool &= driver_features["ehbo"]
        available_drivers = driver_pool - assigned_drivers

        vehicle_pool = active_vehicles.copy()
        if order.get("req_vehicle_liftgate") is True:
            vehicle_pool &= vehicle_features["liftgate"]
        if order.get("req_vehicle_refrigerated") is True:
            vehicle_pool &= vehicle_features["refrigerated"]
        available_vehicles = vehicle_pool - assigned_vehicles

        chosen_driver_idx = None
        chosen_vehicle_idx = None
        compatible_drivers = BitMap()
        for vehicle_idx in available_vehicles:
            compatible_drivers |= allowed_drivers_by_vehicle.get(vehicle_idx, BitMap())

        for driver_idx in available_drivers & compatible_drivers:
            compatible_vehicles = available_vehicles & allowed_vehicles_by_driver.get(driver_idx, BitMap())
            if compatible_vehicles:
                chosen_driver_idx = driver_idx
                chosen_vehicle_idx = min(compatible_vehicles)
                break

        if chosen_driver_idx is not None and chosen_vehicle_idx is not None:
            assigned_drivers.add(chosen_driver_idx)
            assigned_vehicles.add(chosen_vehicle_idx)

            driver_id = drivers_df.loc[drivers_df["driver_index"] == chosen_driver_idx, "driver_id"].values[0]
            vehicle_id = vehicles_df.loc[vehicles_df["vehicle_index"] == chosen_vehicle_idx, "vehicle_id"].values[0]

            results.append(MatchResult(
                order_id=order["order_id"],
                assigned_driver=driver_id,
                assigned_vehicle=vehicle_id,
                status="Fully Matched",
            ))
        else:
            results.append(MatchResult(
                order_id=order["order_id"],
                assigned_driver=None,
                assigned_vehicle=None,
                status="Unfulfilled (Missing Driver or Vehicle)",
            ))

    return results


def run_corematch_logistics(db_or_con: str | duckdb.DuckDBPyConnection = ":memory:") -> Sequence[MatchResult]:
    """
    Run matching against a provided DuckDB connection/cursor or a database file path.
    """
    if isinstance(db_or_con, str):
        with duckdb.connect(db_or_con) as con:
            return _execute_matching(con)
    return _execute_matching(db_or_con)


def run_corematch_logistics_df(db_or_con: str | duckdb.DuckDBPyConnection = ":memory:") -> pd.DataFrame:
    results = run_corematch_logistics(db_or_con)
    return pd.DataFrame([r.model_dump() for r in results])
