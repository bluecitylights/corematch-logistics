import pytest
import duckdb
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.database import init_schema
from features.matching import engine
from features.matching.service import MatchingService, get_matching_service
from features.matching.router import router


def setup_test_db(tmp_path) -> str:
    db_path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(db_path)
    init_schema(con)

    # Needs some demo data to prove matching works
    con.execute("INSERT INTO locations (zip, city, latitude, longitude) VALUES ('1000', 'A', 1, 1)")
    con.execute("INSERT INTO distance_matrix (origin_location_id, dest_location_id, distance_m, travel_time_min) VALUES (1, 2, 1500, 10)")
    con.execute("INSERT INTO distance_matrix (origin_location_id, dest_location_id, distance_m, travel_time_min) VALUES (1, 1, 0, 0)")
    con.execute("INSERT INTO drivers (name, location_id, is_active, skill_adr, skill_ehbo) VALUES ('D1', 1, true, true, false)")
    con.execute("INSERT INTO vehicles (license_plate, location_id, is_active, spec_liftgate, spec_refrigerated) VALUES ('V1', 'AA', 1, true, true, false)")
    con.execute("INSERT INTO orders (destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (1, true, false, true, false)")
    con.execute("INSERT INTO orders (destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (1, false, true, false, false)")

    con.close()
    return db_path


def test_matching_engine(tmp_path):
    db_path = setup_test_db(tmp_path)
    results = engine.run_corematch_logistics(db_path)

    assert len(results) == 2

    # O1 matches perfectly to D1 and V1
    m1 = next(r for r in results if r.order_id == "O1")
    assert m1.status == "Fully Matched"
    assert m1.assigned_driver == "D1"
    assert m1.assigned_vehicle == "V1"

    # O2 fails because D1 doesn't have ehbo
    m2 = next(r for r in results if r.order_id == "O2")
    assert m2.status != "Fully Matched"
    assert m2.assigned_driver is None


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def test_matching_router(tmp_path):
    db_path = setup_test_db(tmp_path)
    con = duckdb.connect(db_path)
    app.dependency_overrides[get_matching_service] = lambda: MatchingService(con)

    resp = client.post("/api/match")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 2
    assert data[0]["order_id"] == "O1"
    assert data[0]["status"] == "Fully Matched"
