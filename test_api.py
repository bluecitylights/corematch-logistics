"""API tests for editing plan order sequences."""

import duckdb
import pytest
from fastapi.testclient import TestClient

import db
from app import app
from engine import init_schema


@pytest.fixture
def plan_api_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "plan-api.duckdb")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    con = duckdb.connect(db_path)
    init_schema(con)
    con.execute("INSERT INTO plans (plan_id, name) VALUES ('PLAN-1', 'Test plan')")
    con.executemany(
        """
        INSERT INTO plan_orders
            (plan_id, order_id, driver_id, vehicle_id, stop_sequence)
        VALUES ('PLAN-1', ?, 'DRV-1', 'VEH-1', ?)
        """,
        [("ORD-1", 1), ("ORD-2", 2), ("ORD-3", 3)],
    )
    con.close()
    return db_path


def _order_sequence(response):
    assert response.status_code == 200, response.text
    return [
        (order["order_id"], order["stop_sequence"])
        for order in response.json()["orders"]
    ]


def test_move_order_up_swaps_with_previous_order(plan_api_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/plans/PLAN-1/orders/ORD-2/move",
            json={"driver_id": "DRV-1", "vehicle_id": "VEH-1", "direction": -1},
        )

    assert _order_sequence(response) == [
        ("ORD-2", 1),
        ("ORD-1", 2),
        ("ORD-3", 3),
    ]


def test_move_order_down_swaps_with_next_order(plan_api_db):
    with TestClient(app) as client:
        response = client.post(
            "/api/plans/PLAN-1/orders/ORD-1/move",
            json={"driver_id": "DRV-1", "vehicle_id": "VEH-1", "direction": 1},
        )

    assert _order_sequence(response) == [
        ("ORD-2", 1),
        ("ORD-1", 2),
        ("ORD-3", 3),
    ]
