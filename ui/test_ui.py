import duckdb
import pytest
from fastapi.testclient import TestClient

from core.database import init_schema
from app import app

client = TestClient(app)

def test_ui_home_page(tmp_path, monkeypatch):
    con = duckdb.connect(str(tmp_path / "ui_test.duckdb"))
    init_schema(con)
    monkeypatch.setattr("core.database._MASTER_CON", con)

    response = client.get("/")
    assert response.status_code == 200
    assert "CoreMatch" in response.text

def test_ui_drivers_page(tmp_path, monkeypatch):
    con = duckdb.connect(str(tmp_path / "ui_test.duckdb"))
    init_schema(con)
    monkeypatch.setattr("core.database._MASTER_CON", con)

    response = client.get("/drivers")
    assert response.status_code == 200

def test_ui_vehicles_page(tmp_path, monkeypatch):
    con = duckdb.connect(str(tmp_path / "ui_test.duckdb"))
    init_schema(con)
    monkeypatch.setattr("core.database._MASTER_CON", con)

    response = client.get("/vehicles")
    assert response.status_code == 200

def test_ui_orders_page(tmp_path, monkeypatch):
    con = duckdb.connect(str(tmp_path / "ui_test.duckdb"))
    init_schema(con)
    monkeypatch.setattr("core.database._MASTER_CON", con)

    response = client.get("/orders")
    assert response.status_code == 200

def test_ui_plans_page(tmp_path, monkeypatch):
    con = duckdb.connect(str(tmp_path / "ui_test.duckdb"))
    init_schema(con)
    monkeypatch.setattr("core.database._MASTER_CON", con)

    response = client.get("/plans")
    assert response.status_code == 200
