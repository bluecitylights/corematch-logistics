"""
Tests for CoreMatch-Logistics engine.

Acceptance criteria:
    AC1 – uv.lock exists (tooling enforcement / reproducible deps)
    AC2 – Idempotency: assigned bitmaps prevent re-assignment
    AC3 – Atomic integrity: only BOTH available → Fully Matched
"""

import os
from pathlib import Path

import duckdb
import pytest
from pyroaring import BitMap

from engine import evaluate_plan_routes, init_schema, run_corematch_logistics


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _make_db(drivers=None, vehicles=None, orders=None) -> str:
    """
    Create a temp DuckDB file, seed it, and return the path.
    Caller must delete it after the test.

    Note: we generate a unique path WITHOUT pre-creating the file because
    DuckDB 1.5+ refuses to open a pre-existing empty/non-DuckDB file.
    """
    import uuid
    # Use the project dir for temp DBs so there are no cross-filesystem issues.
    db_path = str(Path(__file__).parent / f"_test_{uuid.uuid4().hex}.duckdb")
    con = duckdb.connect(db_path)
    init_schema(con)

    con.execute(
        "INSERT INTO locations (location_id, zip, city, latitude, longitude) "
        "VALUES (1, '1000AA', 'CityA', 52.37, 4.89), "
        "       (2, '2000BB', 'CityB', 52.38, 4.90), "
        "       (3, '3000CC', 'Metro', 52.39, 4.91), "
        "       (4, '4000DD', 'Nowhere', 52.00, 4.00)"
    )
    con.execute(
        "INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min) "
        "VALUES ('1000AA', '2000BB', 5000, 10), "
        "       ('2000BB', '1000AA', 5000, 10), "
        "       ('1000AA', '1000AA', 0, 0), "
        "       ('2000BB', '2000BB', 0, 0), "
        "       ('3000CC', '3000CC', 0, 0), "
        "       ('4000DD', '4000DD', 0, 0)"
    )

    if drivers:
        con.executemany(
            "INSERT INTO drivers "
            "(driver_id, location_id, is_active, skill_adr, skill_ehbo) "
            "VALUES (?, ?, ?, ?, ?)",
            drivers,
        )
    if vehicles:
        con.executemany(
            "INSERT INTO vehicles "
            "(vehicle_id, license_plate, location_id, is_active, "
            "spec_liftgate, spec_refrigerated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            vehicles,
        )
    if orders:
        con.executemany(
            "INSERT INTO orders "
            "(order_id, destination_location_id, req_driver_adr, req_driver_ehbo, "
            "req_vehicle_liftgate, req_vehicle_refrigerated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            orders,
        )
    con.close()
    return db_path


# ------------------------------------------------------------------ #
# AC1 – Tooling enforcement                                            #
# ------------------------------------------------------------------ #

class TestToolingEnforcement:
    def test_uv_lock_exists(self):
        """uv.lock must be present so deps are reproducible."""
        lock_path = Path(__file__).parent / "uv.lock"
        assert lock_path.exists(), (
            "uv.lock not found — run `uv lock` or `uv add <pkg>` to generate it."
        )

    def test_required_packages_importable(self):
        """Core packages must be importable (proves uv env is active)."""
        import duckdb        # noqa: F401
        import pyroaring     # noqa: F401
        import pandas        # noqa: F401


# ------------------------------------------------------------------ #
# AC2 – Idempotency & state tracking                                   #
# ------------------------------------------------------------------ #

class TestIdempotency:
    def test_driver_not_reassigned_across_orders(self):
        """A driver matched to order-1 must not appear in order-2."""
        db = _make_db(
            drivers=[
                ("DRV-A", 1, True, False, False),
            ],
            vehicles=[
                ("VEH-A", "AA-00-AA", 1, True, False, False),
                ("VEH-B", "BB-11-BB", 1, True, False, False),
            ],
            orders=[
                ("ORD-1", 1, False, False, False, False),
                ("ORD-2", 1, False, False, False, False),
            ],
        )
        try:
            df = run_corematch_logistics(db)
            matched = df[df["status"] == "Fully Matched"]
            unmatched = df[df["status"] != "Fully Matched"]

            # Only one driver → only one order can be Fully Matched
            assert len(matched) == 1, f"Expected 1 match, got {len(matched)}"
            assert len(unmatched) == 1, f"Expected 1 unfulfilled, got {len(unmatched)}"

            # The same driver must not appear twice
            assigned = matched["assigned_driver"].tolist()
            assert len(assigned) == len(set(assigned)), "Driver re-assigned!"
        finally:
            os.unlink(db)

    def test_vehicle_not_reassigned_across_orders(self):
        """A vehicle matched to order-1 must not appear in order-2."""
        db = _make_db(
            drivers=[
                ("DRV-A", 1, True, False, False),
                ("DRV-B", 1, True, False, False),
            ],
            vehicles=[
                ("VEH-A", "AA-00-AA", 1, True, False, False),
            ],
            orders=[
                ("ORD-1", 1, False, False, False, False),
                ("ORD-2", 1, False, False, False, False),
            ],
        )
        try:
            df = run_corematch_logistics(db)
            matched = df[df["status"] == "Fully Matched"]
            assert len(matched) == 1, f"Expected 1 match, got {len(matched)}"
            assigned = matched["assigned_vehicle"].tolist()
            assert len(assigned) == len(set(assigned)), "Vehicle re-assigned!"
        finally:
            os.unlink(db)

    def test_bitmap_tracks_assignments(self):
        """
        With 3 drivers and 3 vehicles, 3 orders should all be Fully Matched,
        confirming that the bitmap correctly tracks and does NOT block distinct
        resources from being used.
        """
        db = _make_db(
            drivers=[
                ("DRV-1", 2, True, False, False),
                ("DRV-2", 2, True, False, False),
                ("DRV-3", 2, True, False, False),
            ],
            vehicles=[
                ("VEH-1", "P1", 2, True, False, False),
                ("VEH-2", "P2", 2, True, False, False),
                ("VEH-3", "P3", 2, True, False, False),
            ],
            orders=[
                ("ORD-A", 2, False, False, False, False),
                ("ORD-B", 2, False, False, False, False),
                ("ORD-C", 2, False, False, False, False),
            ],
        )
        try:
            df = run_corematch_logistics(db)
            matched = df[df["status"] == "Fully Matched"]
            assert len(matched) == 3, f"Expected 3 matches, got {len(matched)}"
            # All assigned drivers distinct
            assert df["assigned_driver"].nunique() == 3
            # All assigned vehicles distinct
            assert df["assigned_vehicle"].nunique() == 3
        finally:
            os.unlink(db)


# ------------------------------------------------------------------ #
# AC3 – Atomic integrity                                               #
# ------------------------------------------------------------------ #

class TestAtomicIntegrity:
    def test_no_partial_match_when_driver_missing(self):
        """Order with no eligible driver must be Unfulfilled (not half-assigned)."""
        db = _make_db(
            drivers=[
                # Does NOT have ADR — won't satisfy req_driver_adr
                ("DRV-X", 2, True, False, False),
            ],
            vehicles=[
                ("VEH-X", "XX-00-XX", 2, True, False, False),
            ],
            orders=[
                ("ORD-FAIL", 2, True, False, False, False),  # needs ADR
            ],
        )
        try:
            df = run_corematch_logistics(db)
            row = df[df["order_id"] == "ORD-FAIL"].iloc[0]
            assert row["status"] != "Fully Matched", "Should not match without ADR driver"
            assert row["assigned_driver"] is None or str(row["assigned_driver"]) == "None"
            assert row["assigned_vehicle"] is None or str(row["assigned_vehicle"]) == "None"
        finally:
            os.unlink(db)

    def test_no_partial_match_when_vehicle_missing(self):
        """Order with no eligible vehicle must be Unfulfilled (not half-assigned)."""
        db = _make_db(
            drivers=[
                ("DRV-Y", 3, True, False, False),
            ],
            vehicles=[
                # Does NOT have liftgate
                ("VEH-Y", "YY-11-YY", 3, True, False, False),
            ],
            orders=[
                ("ORD-NOLIFT", 3, False, False, True, False),  # needs liftgate
            ],
        )
        try:
            df = run_corematch_logistics(db)
            row = df[df["order_id"] == "ORD-NOLIFT"].iloc[0]
            assert row["status"] != "Fully Matched"
            assert row["assigned_driver"] is None or str(row["assigned_driver"]) == "None"
            assert row["assigned_vehicle"] is None or str(row["assigned_vehicle"]) == "None"
        finally:
            os.unlink(db)

    def test_fully_matched_when_both_available(self):
        """Order is Fully Matched when both a valid driver and vehicle exist."""
        db = _make_db(
            drivers=[
                ("DRV-OK", 1, True, True, True),
            ],
            vehicles=[
                ("VEH-OK", "OK-00-OK", 1, True, True, True),
            ],
            orders=[
                ("ORD-OK", 1, True, True, True, True),
            ],
        )
        try:
            df = run_corematch_logistics(db)
            row = df[df["order_id"] == "ORD-OK"].iloc[0]
            assert row["status"] == "Fully Matched"
            assert row["assigned_driver"] == "DRV-OK"
            assert row["assigned_vehicle"] == "VEH-OK"
        finally:
            os.unlink(db)

    def test_inactive_resources_excluded(self):
        """Inactive drivers/vehicles must never appear in results."""
        db = _make_db(
            drivers=[
                ("DRV-INACTIVE", 2, False, False, False),  # inactive
            ],
            vehicles=[
                ("VEH-INACTIVE", "IN-00-IN", 2, False, False, False),  # inactive
            ],
            orders=[
                ("ORD-INACTIVE", 2, False, False, False, False),
            ],
        )
        try:
            df = run_corematch_logistics(db)
            row = df.iloc[0]
            assert row["status"] != "Fully Matched"
        finally:
            os.unlink(db)

    def test_empty_tables_return_unfulfilled(self):
        """With no drivers/vehicles, every order must be Unfulfilled."""
        db = _make_db(
            orders=[
                ("ORD-EMPTY", 4, False, False, False, False),
            ],
        )
        try:
            df = run_corematch_logistics(db)
            assert len(df) == 1
            assert df.iloc[0]["status"] != "Fully Matched"
        finally:
            os.unlink(db)

    def test_multi_order_mixed_results(self):
        """
        Scenario with one satisfiable order and one impossible order.
        Only the satisfiable one gets Fully Matched.
        """
        db = _make_db(
            drivers=[
                ("DRV-M1", 3, True, False, False),
            ],
            vehicles=[
                ("VEH-M1", "MT-01", 3, True, False, False),
            ],
            orders=[
                ("ORD-GOOD",  3, False, False, False, False),   # satisfiable
                ("ORD-BAD",   3, True,  False, False, False),   # needs ADR, no ADR driver
            ],
        )
        try:
            df = run_corematch_logistics(db)
            good = df[df["order_id"] == "ORD-GOOD"].iloc[0]
            bad  = df[df["order_id"] == "ORD-BAD"].iloc[0]
            assert good["status"] == "Fully Matched"
            assert bad["status"]  != "Fully Matched"
        finally:
            os.unlink(db)


class TestPlanRouteEvaluation:
    def test_multiple_orders_use_actual_matrix_travel_times(self):
        """A route uses each matrix leg, including the return to its start."""
        rows = [
            {
                "plan_id": "PLAN-1",
                "order_id": "ORD-1",
                "driver_id": "DRV-1",
                "vehicle_id": "VEH-1",
                "stop_sequence": 1,
                "start_zip": "1012",
                "destination_zip": "3011",
            },
            {
                "plan_id": "PLAN-1",
                "order_id": "ORD-2",
                "driver_id": "DRV-1",
                "vehicle_id": "VEH-1",
                "stop_sequence": 2,
                "start_zip": "1012",
                "destination_zip": "3511",
            },
        ]
        travel_times = {
            ("1012", "3011"): 48,
            ("3011", "3511"): 38,
            ("3511", "1012"): 42,
        }

        result = evaluate_plan_routes(rows, travel_times)

        assert result["stops"] == [
            {
                "order_id": "ORD-1",
                "driver_id": "DRV-1",
                "vehicle_id": "VEH-1",
                "stop_sequence": 1,
                "origin_zip": "1012",
                "destination_zip": "3011",
                "driving_time_min": 48,
                "departure_time": "09:00",
                "arrival_time": "09:48",
            },
            {
                "order_id": "ORD-2",
                "driver_id": "DRV-1",
                "vehicle_id": "VEH-1",
                "stop_sequence": 2,
                "origin_zip": "3011",
                "destination_zip": "3511",
                "driving_time_min": 38,
                "departure_time": "09:48",
                "arrival_time": "10:26",
            },
        ]
        assert result["routes"] == [
            {
                "plan_id": "PLAN-1",
                "driver_id": "DRV-1",
                "vehicle_id": "VEH-1",
                "start_zip": "1012",
                "last_stop_zip": "3511",
                "return_driving_time_min": 42,
                "return_departure_time": "10:26",
                "return_arrival_time": "11:08",
            }
        ]
