import pytest
import duckdb
from fastapi.testclient import TestClient

from core.database import init_schema
from features.orders.schemas import OrderCreate, OrderUpdate
from features.orders.service import OrderService, get_order_service
from features.orders.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_service_crud(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    ord_service = OrderService(con)
    
    # Create
    order1 = ord_service.create_order(OrderCreate(
        order_id="O1",
        destination_location_id=1,
        req_driver_adr=True,
        req_vehicle_refrigerated=True
    ))
    assert order1.order_id == "O1"
    assert order1.req_driver_adr is True
    assert order1.req_vehicle_refrigerated is True
    assert order1.req_driver_ehbo is False
    
    # List
    assert len(ord_service.list_orders()) == 1
    
    # Update
    order2 = ord_service.update_order("O1", OrderUpdate(req_driver_ehbo=True))
    assert order2.req_driver_ehbo is True
    assert order2.req_driver_adr is True
    
    # Delete
    order3 = ord_service.delete_order("O1")
    assert order3.order_id == "O1"
    assert len(ord_service.list_orders()) == 0

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    app.dependency_overrides[get_order_service] = lambda: OrderService(con)
    
    resp = client.post("/api/orders", json={"order_id": "O2", "destination_location_id": 1, "req_driver_adr": True})
    assert resp.status_code == 200
    assert resp.json()["order_id"] == "O2"
    
    resp = client.patch("/api/orders/O2", json={"req_vehicle_liftgate": True})
    assert resp.status_code == 200
    assert resp.json()["req_vehicle_liftgate"] is True
    
    resp = client.delete("/api/orders/O2")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
