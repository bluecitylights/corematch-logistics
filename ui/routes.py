"""HTML and HTMX routes for the CoreMatch web interface."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from db import DB_PATH, get_db
from engine import run_corematch_logistics
from services.resources import (
    create_driver,
    create_order,
    create_location,
    create_vehicle,
    list_orders,
    list_locations,
    list_resources,
    update_driver,
    update_vehicle,
)


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _bool(val: str | None) -> bool:
    return val in ("on", "true", "1", "yes")


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def _tmpl(request: Request, name: str, ctx: dict):
    return templates.TemplateResponse(request, name, ctx)


def _location_label(location: dict) -> str:
    return f"{location['zip']} {location['city']}"


def _locations_context() -> list[dict]:
    return [
        {**location, "address": _location_label(location)}
        for location in list_locations()
    ]


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
    drivers = list_resources("drivers", include_inactive=True)
    locations = {location["location_id"]: location["address"] for location in _locations_context()}
    rows = [
        (driver["driver_id"], driver["location_id"], driver["is_active"],
        driver["skill_adr"], driver["skill_ehbo"], locations.get(driver["location_id"], "Unknown"))
        for driver in drivers
    ]
    template = "partials/drivers.html" if _is_htmx(request) else "drivers.html"
    return _tmpl(request, template, {"drivers": rows, "locations": _locations_context()})


@router.get("/locations", response_class=HTMLResponse)
async def locations_page(request: Request):
    locations = _locations_context()
    return _tmpl(request, "locations.html", {"locations": locations})


@router.post("/locations", response_class=HTMLResponse)
async def add_location(
    request: Request,
    zip: str = Form(...),
    city: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
):
    create_location({
        "zip": zip,
        "city": city,
        "latitude": latitude,
        "longitude": longitude,
    })
    return await locations_page(request)


@router.post("/drivers", response_class=HTMLResponse)
async def add_driver(
    request: Request,
    driver_id: str = Form(...),
    location_id: int = Form(...),
    skill_adr: str | None = Form(None),
    skill_ehbo: str | None = Form(None),
):
    create_driver({
        "driver_id": driver_id,
        "location_id": location_id,
        "skill_adr": _bool(skill_adr),
        "skill_ehbo": _bool(skill_ehbo),
    })
    return await drivers_page(request)


@router.delete("/drivers/{driver_id}", response_class=HTMLResponse)
async def deactivate_driver(driver_id: str, request: Request):
    update_driver(driver_id, {"is_active": False})
    return await drivers_page(request)


@router.get("/vehicles", response_class=HTMLResponse)
async def vehicles_page(request: Request):
    vehicles = list_resources("vehicles", include_inactive=True)
    locations = {location["location_id"]: location["address"] for location in _locations_context()}
    rows = [
        (vehicle["vehicle_id"], vehicle["license_plate"], vehicle["location_id"],
         vehicle["is_active"], vehicle["spec_liftgate"], vehicle["spec_refrigerated"],
         locations.get(vehicle["location_id"], "Unknown"))
        for vehicle in vehicles
    ]
    template = "partials/vehicles.html" if _is_htmx(request) else "vehicles.html"
    return _tmpl(request, template, {"vehicles": rows, "locations": _locations_context()})


@router.post("/vehicles", response_class=HTMLResponse)
async def add_vehicle(
    request: Request,
    vehicle_id: str = Form(...),
    license_plate: str = Form(...),
    location_id: int = Form(...),
    spec_liftgate: str | None = Form(None),
    spec_refrigerated: str | None = Form(None),
):
    create_vehicle({
        "vehicle_id": vehicle_id,
        "license_plate": license_plate,
        "location_id": location_id,
        "spec_liftgate": _bool(spec_liftgate),
        "spec_refrigerated": _bool(spec_refrigerated),
    })
    return await vehicles_page(request)


@router.delete("/vehicles/{vehicle_id}", response_class=HTMLResponse)
async def deactivate_vehicle(vehicle_id: str, request: Request):
    update_vehicle(vehicle_id, {"is_active": False})
    return await vehicles_page(request)


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    orders = list_orders()
    locations = {location["location_id"]: location["address"] for location in _locations_context()}
    rows = [
        (order["order_id"], order["destination_location_id"], order["req_driver_adr"],
         order["req_driver_ehbo"], order["req_vehicle_liftgate"],
         order["req_vehicle_refrigerated"],
         locations.get(order["destination_location_id"], "Unknown"))
        for order in orders
    ]
    template = "partials/orders.html" if _is_htmx(request) else "orders.html"
    return _tmpl(request, template, {"orders": rows, "locations": _locations_context()})


@router.post("/orders", response_class=HTMLResponse)
async def add_order(
    request: Request,
    order_id: str = Form(...),
    destination_location_id: int = Form(...),
    req_driver_adr: str | None = Form(None),
    req_driver_ehbo: str | None = Form(None),
    req_vehicle_liftgate: str | None = Form(None),
    req_vehicle_refrigerated: str | None = Form(None),
):
    create_order({
        "order_id": order_id,
        "destination_location_id": destination_location_id,
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
