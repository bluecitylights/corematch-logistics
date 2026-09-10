"""HTML and HTMX routes for the CoreMatch web interface."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from api.routes import (
    api_create_driver,
    api_create_order,
    api_create_vehicle,
    api_delete_driver,
    api_delete_vehicle,
    api_drivers,
    api_orders,
    api_vehicles,
)
from db import DB_PATH, get_db
from engine import run_corematch_logistics


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _bool(val: str | None) -> bool:
    return val in ("on", "true", "1", "yes")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _tmpl(request: Request, name: str, ctx: dict):
    return templates.TemplateResponse(request, name, ctx)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    with get_db() as con:
        driver_count = con.execute("SELECT COUNT(*) FROM drivers WHERE is_active").fetchone()[0]
        vehicle_count = con.execute("SELECT COUNT(*) FROM vehicles WHERE is_active").fetchone()[0]
        order_count = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    return _tmpl(request, "index.html", {
        "driver_count": driver_count,
        "vehicle_count": vehicle_count,
        "order_count": order_count,
    })


@router.get("/drivers", response_class=HTMLResponse)
async def drivers_page(request: Request):
    drivers = await api_drivers(include_inactive=True)
    rows = [
        (driver["driver_id"], driver["location"], driver["is_active"],
         driver["skill_adr"], driver["skill_ehbo"])
        for driver in drivers
    ]
    template = "partials/drivers.html" if _is_htmx(request) else "drivers.html"
    return _tmpl(request, template, {"drivers": rows})


@router.post("/drivers", response_class=HTMLResponse)
async def add_driver(
    request: Request,
    driver_id: str = Form(...),
    location: str = Form(...),
    skill_adr: str | None = Form(None),
    skill_ehbo: str | None = Form(None),
):
    await api_create_driver({
        "driver_id": driver_id,
        "location": location,
        "skill_adr": _bool(skill_adr),
        "skill_ehbo": _bool(skill_ehbo),
    })
    return await drivers_page(request)


@router.delete("/drivers/{driver_id}", response_class=HTMLResponse)
async def deactivate_driver(driver_id: str, request: Request):
    await api_delete_driver(driver_id)
    return await drivers_page(request)


@router.get("/vehicles", response_class=HTMLResponse)
async def vehicles_page(request: Request):
    vehicles = await api_vehicles(include_inactive=True)
    rows = [
        (vehicle["vehicle_id"], vehicle["license_plate"], vehicle["location"],
         vehicle["is_active"], vehicle["spec_liftgate"], vehicle["spec_refrigerated"])
        for vehicle in vehicles
    ]
    template = "partials/vehicles.html" if _is_htmx(request) else "vehicles.html"
    return _tmpl(request, template, {"vehicles": rows})


@router.post("/vehicles", response_class=HTMLResponse)
async def add_vehicle(
    request: Request,
    vehicle_id: str = Form(...),
    license_plate: str = Form(...),
    location: str = Form(...),
    spec_liftgate: str | None = Form(None),
    spec_refrigerated: str | None = Form(None),
):
    await api_create_vehicle({
        "vehicle_id": vehicle_id,
        "license_plate": license_plate,
        "location": location,
        "spec_liftgate": _bool(spec_liftgate),
        "spec_refrigerated": _bool(spec_refrigerated),
    })
    return await vehicles_page(request)


@router.delete("/vehicles/{vehicle_id}", response_class=HTMLResponse)
async def deactivate_vehicle(vehicle_id: str, request: Request):
    await api_delete_vehicle(vehicle_id)
    return await vehicles_page(request)


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    orders = await api_orders()
    rows = [
        (order["order_id"], order["destination"], order["req_driver_adr"],
         order["req_driver_ehbo"], order["req_vehicle_liftgate"],
         order["req_vehicle_refrigerated"])
        for order in orders
    ]
    template = "partials/orders.html" if _is_htmx(request) else "orders.html"
    return _tmpl(request, template, {"orders": rows})


@router.post("/orders", response_class=HTMLResponse)
async def add_order(
    request: Request,
    order_id: str = Form(...),
    destination: str = Form(...),
    req_driver_adr: str | None = Form(None),
    req_driver_ehbo: str | None = Form(None),
    req_vehicle_liftgate: str | None = Form(None),
    req_vehicle_refrigerated: str | None = Form(None),
):
    await api_create_order({
        "order_id": order_id,
        "destination": destination,
        "req_driver_adr": _bool(req_driver_adr),
        "req_driver_ehbo": _bool(req_driver_ehbo),
        "req_vehicle_liftgate": _bool(req_vehicle_liftgate),
        "req_vehicle_refrigerated": _bool(req_vehicle_refrigerated),
    })
    return await orders_page(request)


@router.post("/match", response_class=HTMLResponse)
async def run_match(request: Request):
    results = run_corematch_logistics(DB_PATH).to_dict(orient="records")
    return _tmpl(request, "partials/match_results.html", {"results": results})


@router.post("/seed", response_class=HTMLResponse)
async def seed_demo(request: Request):
    from engine import _seed_demo

    with get_db() as con:
        if con.execute("SELECT COUNT(*) FROM drivers").fetchone()[0] == 0:
            _seed_demo(con)
    return HTMLResponse('<p class="text-green-600 font-semibold">Demo data seeded ✓</p>')
