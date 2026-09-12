import pytest
import duckdb
from fastapi.testclient import TestClient

from core.database import init_schema
from features.plans.schemas import PlanCreate, PlanOrderAdd, PlanRouteSwitch
from features.plans import service
from features.plans.service import PlanService, get_plan_service
from features.plans.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    
    # Seeding prerequisites
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (2, '2000', 'B', 2, 2)")
    con.execute("INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min) VALUES ('1000', '1000', 0, 0)")
    con.execute("INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min) VALUES ('1000', '2000', 100, 10)")
    con.execute("INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min) VALUES ('2000', '1000', 100, 10)")
    con.execute("INSERT INTO drivers (driver_id, location_id, is_active, skill_adr, skill_ehbo) VALUES ('D1', 1, true, true, false)")
    con.execute("INSERT INTO vehicles (vehicle_id, license_plate, location_id, is_active, spec_liftgate, spec_refrigerated) VALUES ('V1', 'AA', 1, true, true, false)")
    con.execute("INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES ('O1', 2, false, false, false, false)")
    con.execute("INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES ('O2', 1, false, false, false, false)")
    return con

def test_plan_crud(tmp_path):
    con = setup_db(tmp_path)
    
    p = service.create_plan(con, PlanCreate(plan_id="P1", name="Test Plan"))
    assert p.plan_id == "P1"
    
    # Add order
    d = service.add_plan_order(con, "P1", PlanOrderAdd(order_id="O1", driver_id="D1", vehicle_id="V1"))
    assert len(d.assignments) == 1
    assert d.assignments[0].order_id == "O1"
    assert d.assignments[0].stop_sequence == 1
    
    # Evaluation
    d = service.evaluate_plan(con, "P1")
    assert len(d.evaluation.stops) == 1
    assert d.evaluation.stops[0].driving_time_min == 10
    
    # Move order (add second first)
    service.add_plan_order(con, "P1", PlanOrderAdd(order_id="O2", driver_id="D1", vehicle_id="V1"))
    d = service.move_plan_order(con, "P1", "D1", "V1", "O1", direction=1) # O1 moves down
    assigned_o1 = next(a for a in d.assignments if a.order_id == "O1")
    assert assigned_o1.stop_sequence == 2

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_plan_router(tmp_path):
    con = setup_db(tmp_path)
    app.dependency_overrides[get_plan_service] = lambda: PlanService(con)
    
    resp = client.post("/api/plans", json={"plan_id": "P2", "name": "Plan 2"})
    assert resp.status_code == 200
    assert resp.json()["plan_id"] == "P2"
    
    resp = client.get("/api/plans")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
