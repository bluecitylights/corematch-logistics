import pytest
import duckdb
import os
from typing import Any

from core.database import init_schema
from mcp_tools import server

def setup_db(tmp_path) -> str:
    db_path = str(tmp_path / "test.duckdb")
    con = duckdb.connect(db_path)
    init_schema(con)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    con.close()
    return db_path

def test_mcp_tools(tmp_path, monkeypatch):
    db_path = setup_db(tmp_path)
    # Mock DB_PATH so mcp tools hit the right path
    monkeypatch.setenv("COREMATCH_DB_PATH", db_path)
    # Have to forcibly set it in config since it's already imported probably
    from core import config
    monkeypatch.setattr(config, "DB_PATH", db_path)
    from core.database import get_db
    import duckdb
    import contextlib
    
    @contextlib.contextmanager
    def mock_get_db():
        con = duckdb.connect(db_path)
        try:
            yield con
        finally:
            con.close()
            
    monkeypatch.setattr("mcp_tools.server.get_db", mock_get_db)
    
    # Also patch generate_plan's usage of DB_PATH
    from features.plans import service as plan_service
    monkeypatch.setattr(plan_service, "DB_PATH", db_path)
    # matching_engine does not import DB_PATH directly at top level either. 
    # core.config.DB_PATH is already patched on line 23.
    # 1. Driver
    drv = server.create_driver("D1", 1, True, False)
    assert drv["driver_id"] == "D1"
    
    drv_list = server.list_drivers()
    assert len(drv_list) == 1
    
    # 2. Vehicle
    veh = server.create_vehicle("V1", "AA", 1, True, False)
    assert veh["vehicle_id"] == "V1"
    
    # 3. Order
    ord1 = server.create_order("O1", 1, True, False, True, False)
    assert ord1["order_id"] == "O1"
    
    ord_list = server.list_orders()
    assert len(ord_list) == 1
    
    # 4. Matching setup (needs distance)
    con = duckdb.connect(db_path)
    con.execute("INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min) VALUES ('1000', '1000', 0, 0)")
    con.close()
    
    matches = server.run_matching()
    assert len(matches) == 1
    assert matches[0]["status"] == "Fully Matched"
    
    # 5. Plans
    plan = server.create_plan("P1", "Test")
    assert plan["plan_id"] == "P1"
    
    # Generate directly uses match 
    gen = server.generate_plan("P1")
    assert len(gen["assignments"]) == 1
    assert gen["assignments"][0]["order_id"] == "O1"

