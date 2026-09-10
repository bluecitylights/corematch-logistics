"""
CoreMatch-Logistics: high-performance dual-resource allocation engine.

Uses DuckDB for relational state persistence and pyroaring BitMaps for
sub-millisecond set intersections during driver + vehicle matching.

Run:  uv run -m engine.matching
"""

import duckdb
from pyroaring import BitMap
import pandas as pd
from pathlib import Path


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Apply schema.sql to an existing connection."""
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    con.execute(schema_path.read_text())


def run_corematch_logistics(db_path: str = ":memory:") -> pd.DataFrame:
    """
    Load drivers, vehicles, and orders from DuckDB; perform bitmap-accelerated
    dual-resource matching; return a DataFrame of assignment results.

    Parameters
    ----------
    db_path:
        DuckDB database file path, or ":memory:" for an ephemeral in-process DB.

    Returns
    -------
    pd.DataFrame with columns:
        order_id, assigned_driver, assigned_vehicle, status
    """
    con = duckdb.connect(db_path)

    # ------------------------------------------------------------------ #
    # 1. Load relational state into DataFrames                            #
    # ------------------------------------------------------------------ #
    drivers_df = con.execute("SELECT * FROM drivers").fetchdf()
    vehicles_df = con.execute("SELECT * FROM vehicles").fetchdf()
    orders_df = con.execute("SELECT * FROM orders").fetchdf()

    # ------------------------------------------------------------------ #
    # 2. Build BitMap indexes                                              #
    # ------------------------------------------------------------------ #
    # Active pools
    active_drivers = BitMap(
        drivers_df.loc[drivers_df["is_active"] == True, "driver_index"].tolist()
    )
    active_vehicles = BitMap(
        vehicles_df.loc[vehicles_df["is_active"] == True, "vehicle_index"].tolist()
    )

    # Location indexes  (destination → set of driver/vehicle indexes at that location)
    driver_locs: dict[int, BitMap] = {
        loc: BitMap(
            drivers_df.loc[drivers_df["location_id"] == loc, "driver_index"].tolist()
        )
        for loc in drivers_df["location_id"].dropna().unique()
    }
    vehicle_locs: dict[int, BitMap] = {
        loc: BitMap(
            vehicles_df.loc[vehicles_df["location_id"] == loc, "vehicle_index"].tolist()
        )
        for loc in vehicles_df["location_id"].dropna().unique()
    }

    # Skill / spec feature indexes
    driver_features: dict[str, BitMap] = {
        "adr": BitMap(
            drivers_df.loc[drivers_df["skill_adr"] == True, "driver_index"].tolist()
        ),
        "ehbo": BitMap(
            drivers_df.loc[drivers_df["skill_ehbo"] == True, "driver_index"].tolist()
        ),
    }
    vehicle_features: dict[str, BitMap] = {
        "liftgate": BitMap(
            vehicles_df.loc[
                vehicles_df["spec_liftgate"] == True, "vehicle_index"
            ].tolist()
        ),
        "refrigerated": BitMap(
            vehicles_df.loc[
                vehicles_df["spec_refrigerated"] == True, "vehicle_index"
            ].tolist()
        ),
    }

    # ------------------------------------------------------------------ #
    # 3. Matching loop — greedy, first-available, idempotent              #
    # ------------------------------------------------------------------ #
    assigned_drivers: BitMap = BitMap()   # tracks used drivers across orders
    assigned_vehicles: BitMap = BitMap()  # tracks used vehicles across orders
    results: list[dict] = []

    for _, order in orders_df.iterrows():
        dest = order.get("destination_location_id")

        # --- Driver candidate pool ---
        if dest and dest in driver_locs:
            # Restrict to drivers located at the order's destination
            driver_pool = driver_locs[dest] & active_drivers
        else:
            driver_pool = active_drivers.copy()

        if order.get("req_driver_adr") is True:
            driver_pool &= driver_features["adr"]
        if order.get("req_driver_ehbo") is True:
            driver_pool &= driver_features["ehbo"]

        # Remove already-assigned drivers (idempotency guard)
        available_drivers = driver_pool - assigned_drivers

        # --- Vehicle candidate pool ---
        if dest and dest in vehicle_locs:
            vehicle_pool = vehicle_locs[dest] & active_vehicles
        else:
            vehicle_pool = active_vehicles.copy()

        if order.get("req_vehicle_liftgate") is True:
            vehicle_pool &= vehicle_features["liftgate"]
        if order.get("req_vehicle_refrigerated") is True:
            vehicle_pool &= vehicle_features["refrigerated"]

        # Remove already-assigned vehicles (idempotency guard)
        available_vehicles = vehicle_pool - assigned_vehicles

        # --- Atomic dual assignment ---
        # Both must be available; otherwise the order is unfulfilled entirely.
        if available_drivers and available_vehicles:
            chosen_driver_idx = min(available_drivers)
            chosen_vehicle_idx = min(available_vehicles)

            # Commit to the assignment bitmaps
            assigned_drivers.add(chosen_driver_idx)
            assigned_vehicles.add(chosen_vehicle_idx)

            driver_id = drivers_df.loc[
                drivers_df["driver_index"] == chosen_driver_idx, "driver_id"
            ].values[0]
            vehicle_id = vehicles_df.loc[
                vehicles_df["vehicle_index"] == chosen_vehicle_idx, "vehicle_id"
            ].values[0]

            results.append(
                {
                    "order_id": order["order_id"],
                    "assigned_driver": driver_id,
                    "assigned_vehicle": vehicle_id,
                    "status": "Fully Matched",
                }
            )
        else:
            # Atomic failure: neither resource is committed
            results.append(
                {
                    "order_id": order["order_id"],
                    "assigned_driver": None,
                    "assigned_vehicle": None,
                    "status": "Unfulfilled (Missing Driver or Vehicle)",
                }
            )

    con.close()
    return pd.DataFrame(results)


# --------------------------------------------------------------------------- #
# Demo entry-point                                                              #
# --------------------------------------------------------------------------- #
def _seed_demo(con: duckdb.DuckDBPyConnection) -> None:
    """Insert a small representative dataset for a quick smoke-test."""
    demo_locations = [
        ("1012", "Amsterdam", 52.3728, 4.8936),
        ("3011", "Rotterdam", 51.9244, 4.4777),
        ("3511", "Utrecht", 52.0907, 5.1214),
    ]
    con.executemany(
        """
        INSERT INTO locations (zip, city, latitude, longitude)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (zip) DO NOTHING
        """,
        demo_locations,
    )
    location_ids = {
        city: location_id
        for location_id, city in con.execute(
            "SELECT location_id, city FROM locations WHERE city IN ('Amsterdam', 'Rotterdam', 'Utrecht')"
        ).fetchall()
    }
    con.executemany(
        "INSERT INTO drivers (driver_id, location_id, is_active, skill_adr, skill_ehbo) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            ("DRV-001", location_ids["Amsterdam"], True, True, False),
            ("DRV-002", location_ids["Amsterdam"], True, False, True),
            ("DRV-003", location_ids["Rotterdam"], True, True, True),
            ("DRV-004", location_ids["Utrecht"], True, False, False),
            ("DRV-005", location_ids["Amsterdam"], False, True, True),
        ],
    )
    con.executemany(
        "INSERT INTO vehicles (vehicle_id, license_plate, location_id, is_active, "
        "spec_liftgate, spec_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("VEH-001", "AB-12-CD", location_ids["Amsterdam"], True, True, False),
            ("VEH-002", "EF-34-GH", location_ids["Amsterdam"], True, False, True),
            ("VEH-003", "IJ-56-KL", location_ids["Rotterdam"], True, True, True),
            ("VEH-004", "MN-78-OP", location_ids["Utrecht"], True, False, False),
        ],
    )
    con.executemany(
        "INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, "
        "req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("ORD-001", location_ids["Amsterdam"], True, False, True, False),
            ("ORD-002", location_ids["Amsterdam"], False, True, False, True),
            ("ORD-003", location_ids["Rotterdam"], False, False, False, False),
            ("ORD-004", location_ids["Rotterdam"], True, True, False, False),
            ("ORD-005", location_ids["Utrecht"], True, False, False, False),
        ],
    )


if __name__ == "__main__":
    import os

    tmp_db = str(Path(__file__).parent.parent / "_demo.duckdb")
    try:
        con = duckdb.connect(tmp_db)
        init_schema(con)
        _seed_demo(con)
        con.close()

        df = run_corematch_logistics(tmp_db)
        print("\n=== CoreMatch-Logistics Demo Results ===")
        print(df.to_string(index=False))
    finally:
        if Path(tmp_db).exists():
            os.unlink(tmp_db)
