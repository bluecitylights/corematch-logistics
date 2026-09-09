"""
CoreMatch-Logistics — FastAPI web application.

Routes:
  GET  /                   → dashboard (counts + recent matches)
  GET  /drivers            → drivers list (HTMX fragment or full page)
  GET  /vehicles           → vehicles list
  GET  /orders             → orders list
  POST /match              → run the matching engine, return results fragment
  POST /drivers            → add a driver
  POST /vehicles           → add a vehicle
  POST /orders             → add an order
  DELETE /drivers/{id}     → deactivate driver
  DELETE /vehicles/{id}    → deactivate vehicle
"""

import os
import time
from pathlib import Path

import duckdb
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from engine import init_schema, run_corematch_logistics

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "corematch.duckdb"))

app = FastAPI(title="CoreMatch-Logistics")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db() -> duckdb.DuckDBPyConnection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(DB_PATH, read_only=False)


def ensure_schema():
    con = get_db()
    tables = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
    ).fetchall()}
    if "drivers" not in tables:
        init_schema(con)
    con.close()


@app.on_event("startup")
async def startup():
    for attempt in range(5):
        try:
            ensure_schema()
            break
        except Exception as e:
            if attempt == 4:
                raise
            print(f"[app] DB not ready ({e}), retrying in 2s…", flush=True)
            time.sleep(2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bool(val: str | None) -> bool:
    return val in ("on", "true", "1", "yes")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _tmpl(request: Request, name: str, ctx: dict):
    """Render a template with the new Starlette 1.6+ API."""
    return templates.TemplateResponse(request, name, ctx)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    con = get_db()
    driver_count  = con.execute("SELECT COUNT(*) FROM drivers WHERE is_active").fetchone()[0]
    vehicle_count = con.execute("SELECT COUNT(*) FROM vehicles WHERE is_active").fetchone()[0]
    order_count   = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    con.close()
    return _tmpl(request, "index.html", {
        "driver_count": driver_count,
        "vehicle_count": vehicle_count,
        "order_count": order_count,
    })


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------

@app.get("/drivers", response_class=HTMLResponse)
async def drivers_page(request: Request):
    con = get_db()
    rows = con.execute(
        "SELECT driver_id, location, is_active, skill_adr, skill_ehbo FROM drivers ORDER BY driver_index"
    ).fetchall()
    con.close()
    template = "partials/drivers.html" if _is_htmx(request) else "drivers.html"
    return _tmpl(request, template, {"drivers": rows})


@app.post("/drivers", response_class=HTMLResponse)
async def add_driver(
    request: Request,
    driver_id: str = Form(...),
    location: str = Form(...),
    skill_adr: str | None = Form(None),
    skill_ehbo: str | None = Form(None),
):
    con = get_db()
    con.execute(
        "INSERT INTO drivers (driver_id, location, skill_adr, skill_ehbo) VALUES (?,?,?,?)",
        [driver_id, location, _bool(skill_adr), _bool(skill_ehbo)],
    )
    con.close()
    return await drivers_page(request)


@app.delete("/drivers/{driver_id}", response_class=HTMLResponse)
async def deactivate_driver(driver_id: str, request: Request):
    con = get_db()
    con.execute("UPDATE drivers SET is_active=false WHERE driver_id=?", [driver_id])
    con.close()
    return await drivers_page(request)


# ---------------------------------------------------------------------------
# Vehicles
# ---------------------------------------------------------------------------

@app.get("/vehicles", response_class=HTMLResponse)
async def vehicles_page(request: Request):
    con = get_db()
    rows = con.execute(
        "SELECT vehicle_id, license_plate, location, is_active, spec_liftgate, spec_refrigerated "
        "FROM vehicles ORDER BY vehicle_index"
    ).fetchall()
    con.close()
    template = "partials/vehicles.html" if _is_htmx(request) else "vehicles.html"
    return _tmpl(request, template, {"vehicles": rows})


@app.post("/vehicles", response_class=HTMLResponse)
async def add_vehicle(
    request: Request,
    vehicle_id: str = Form(...),
    license_plate: str = Form(...),
    location: str = Form(...),
    spec_liftgate: str | None = Form(None),
    spec_refrigerated: str | None = Form(None),
):
    con = get_db()
    con.execute(
        "INSERT INTO vehicles (vehicle_id, license_plate, location, spec_liftgate, spec_refrigerated) "
        "VALUES (?,?,?,?,?)",
        [vehicle_id, license_plate, location, _bool(spec_liftgate), _bool(spec_refrigerated)],
    )
    con.close()
    return await vehicles_page(request)


@app.delete("/vehicles/{vehicle_id}", response_class=HTMLResponse)
async def deactivate_vehicle(vehicle_id: str, request: Request):
    con = get_db()
    con.execute("UPDATE vehicles SET is_active=false WHERE vehicle_id=?", [vehicle_id])
    con.close()
    return await vehicles_page(request)


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    con = get_db()
    rows = con.execute(
        "SELECT order_id, destination, req_driver_adr, req_driver_ehbo, "
        "req_vehicle_liftgate, req_vehicle_refrigerated FROM orders ORDER BY order_id"
    ).fetchall()
    con.close()
    template = "partials/orders.html" if _is_htmx(request) else "orders.html"
    return _tmpl(request, template, {"orders": rows})


@app.post("/orders", response_class=HTMLResponse)
async def add_order(
    request: Request,
    order_id: str = Form(...),
    destination: str = Form(...),
    req_driver_adr: str | None = Form(None),
    req_driver_ehbo: str | None = Form(None),
    req_vehicle_liftgate: str | None = Form(None),
    req_vehicle_refrigerated: str | None = Form(None),
):
    con = get_db()
    con.execute(
        "INSERT INTO orders (order_id, destination, req_driver_adr, req_driver_ehbo, "
        "req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?,?,?,?,?,?)",
        [order_id, destination,
         _bool(req_driver_adr), _bool(req_driver_ehbo),
         _bool(req_vehicle_liftgate), _bool(req_vehicle_refrigerated)],
    )
    con.close()
    return await orders_page(request)


# ---------------------------------------------------------------------------
# Run matching engine
# ---------------------------------------------------------------------------

@app.post("/match", response_class=HTMLResponse)
async def run_match(request: Request):
    results_df = run_corematch_logistics(DB_PATH)
    results = results_df.to_dict(orient="records")
    return _tmpl(request, "partials/match_results.html", {"results": results})


# ---------------------------------------------------------------------------
# Seed demo data
# ---------------------------------------------------------------------------

@app.post("/seed", response_class=HTMLResponse)
async def seed_demo(request: Request):
    from engine import _seed_demo
    con = get_db()
    if con.execute("SELECT COUNT(*) FROM drivers").fetchone()[0] == 0:
        _seed_demo(con)
    con.close()
    return HTMLResponse('<p class="text-green-600 font-semibold">Demo data seeded ✓</p>')
