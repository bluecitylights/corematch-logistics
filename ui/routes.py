"""HTML page routes rendering Jinja2 templates via Vertical Slice Services."""

from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.database import get_db
from core.config import DB_PATH
from features.locations import service as location_service, schemas as location_schemas
from features.drivers import service as driver_service, schemas as driver_schemas
from features.vehicles import service as vehicle_service, schemas as vehicle_schemas
from features.orders import service as order_service, schemas as order_schemas
from features.plans import service as plan_service, schemas as plan_schemas
from features.matching import engine as matching_engine

router = APIRouter(tags=["ui"])

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _tmpl(request: Request, name: str, context: dict | None = None) -> HTMLResponse:
    ctx = {"request": request}
    if context:
        ctx.update(context)
    return templates.TemplateResponse(name, ctx)


def _is_htmx(request: Request) -> bool:
    return "hx-request" in request.headers


def _bool(val: str | None) -> bool:
    return val == "on"


def _locations_context() -> list[dict]:
    with get_db() as con:
        return [
            {
                "location_id": l.location_id,
                "zip": l.zip,
                "city": l.city,
                "address": f"{l.zip} {l.city}",
            }
            for l in location_service.list_locations(con)
        ]


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    with get_db() as con:
        driver_count = con.execute("SELECT COUNT(*) FROM drivers WHERE is_active").fetchone()[0]
        vehicle_count = con.execute("SELECT COUNT(*) FROM vehicles WHERE is_active").fetchone()[0]
        order_count = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    return _tmpl(
        request,
        "home.html",
        {
            "driver_count": driver_count,
            "vehicle_count": vehicle_count,
            "order_count": order_count,
        },
    )


@router.get("/locations", response_class=HTMLResponse)
async def locations_page(request: Request):
    with get_db() as con:
        locations = location_service.list_locations(con)
    rows = [
        (location.zip, location.city, location.latitude, location.longitude)
        for location in locations
    ]
    template = "partials/locations.html" if _is_htmx(request) else "locations.html"
    return _tmpl(request, template, {"locations": rows})


@router.get("/drivers", response_class=HTMLResponse)
async def drivers_page(request: Request):
    with get_db() as con:
        drivers = driver_service.list_drivers(con, include_inactive=True)
    locations = {location["location_id"]: location["address"] for location in _locations_context()}
    rows = [
        (
            driver.driver_id,
            driver.location_id,
            driver.is_active,
            driver.skill_adr,
            driver.skill_ehbo,
            locations.get(driver.location_id, "Unknown"),
            getattr(driver, "driver_index", 0)
        )
        for driver in drivers
    ]
    template = "partials/drivers.html" if _is_htmx(request) else "drivers.html"
    return _tmpl(request, template, {"drivers": rows, "locations": _locations_context()})


@router.get("/plans", response_class=HTMLResponse)
async def plans_page(
    request: Request,
    validation: dict | None = None,
):
    with get_db() as con:
        plan_models = plan_service.list_plans(con)
        plans = []
        for p in plan_models:
            d = plan_service.get_plan(con, p.plan_id)
            if d:
                # Format to dict-like lists to match what template expects (or we can just pass Pydantic models directly)
                plans.append({
                    "plan_id": d.plan_id,
                    "name": d.name,
                    "orders": [{"order_id": a.order_id, "driver_id": a.driver_id, "vehicle_id": a.vehicle_id, "stop_sequence": a.stop_sequence} for a in d.assignments],
                    "evaluation": {
                        "stops": [s.model_dump() for s in d.evaluation.stops],
                        "routes": [r.model_dump() for r in d.evaluation.routes]
                    } if d.evaluation else {"stops": [], "routes": []}
                })

        drivers = [{"driver_id": d.driver_id} for d in driver_service.list_drivers(con)]
        vehicles = [{"vehicle_id": v.vehicle_id} for v in vehicle_service.list_vehicles(con)]
        orders_raw = order_service.list_orders(con)
        
        order_locations = {l["location_id"]: l["address"] for l in _locations_context()}
        orders = []
        for o in orders_raw:
            o_dict = o.model_dump()
            o_dict["destination_label"] = order_locations.get(o.destination_location_id, "Unknown")
            orders.append(o_dict)

    for plan in plans:
        assigned_order_ids = {order["order_id"] for order in plan["orders"]}
        plan["available_orders"] = [
            order for order in orders
            if order["order_id"] not in assigned_order_ids
        ]
        
        if validation:
            plan["validation"] = validation
            
    return _tmpl(
        request,
        "plans.html",
        {
            "plans": plans,
            "drivers": drivers,
            "vehicles": vehicles,
            "orders": orders,
            "validation": validation,
        },
    )


@router.post("/plans", response_class=HTMLResponse)
async def add_plan(
    request: Request,
    plan_id: str = Form(...),
    name: str = Form(...),
):
    with get_db() as con:
        plan_service.create_plan(con, plan_schemas.PlanCreate(plan_id=plan_id, name=name))
    return await plans_page(request)


@router.post("/plans/{plan_id}/match", response_class=HTMLResponse)
async def run_plan_match(plan_id: str, request: Request):
    with get_db() as con:
        plan_service.generate_plan(con, plan_id)
    return await plans_page(request)


@router.post("/plans/{plan_id}/evaluate", response_class=HTMLResponse)
async def evaluate_plan_page(plan_id: str, request: Request):
    with get_db() as con:
        plan_service.evaluate_plan(con, plan_id)
    return await plans_page(request)


@router.post("/plans/{plan_id}/validate", response_class=HTMLResponse)
async def validate_plan_page(plan_id: str, request: Request):
    with get_db() as con:
        res = plan_service.validate_plan(con, plan_id)
    return await plans_page(request, validation={"errors": res.errors} if res else None)


@router.post("/plans/{plan_id}/routes", response_class=HTMLResponse)
async def switch_plan_route_page(
    plan_id: str,
    request: Request,
    current_driver_id: str = Form(...),
    current_vehicle_id: str = Form(...),
    driver_id: str = Form(...),
    vehicle_id: str = Form(...),
):
    with get_db() as con:
        plan_service.switch_plan_route(
            con,
            plan_id,
            current_driver_id,
            current_vehicle_id,
            plan_schemas.PlanRouteSwitch(driver_id=driver_id, vehicle_id=vehicle_id)
        )
    return await plans_page(request)


@router.post("/plans/{plan_id}/orders/{order_id}/move", response_class=HTMLResponse)
async def move_plan_order_page(
    plan_id: str,
    order_id: str,
    request: Request,
    driver_id: str = Form(...),
    vehicle_id: str = Form(...),
    direction: int = Form(...),
):
    with get_db() as con:
        plan_service.move_plan_order(con, plan_id, driver_id, vehicle_id, order_id, direction)
    return await plans_page(request)


@router.post("/plans/{plan_id}/orders", response_class=HTMLResponse)
async def add_plan_order_page(
    plan_id: str,
    request: Request,
    driver_id: str = Form(...),
    vehicle_id: str = Form(...),
    order_id: str = Form(...),
):
    with get_db() as con:
        plan_service.add_plan_order(
            con,
            plan_id,
            plan_schemas.PlanOrderAdd(driver_id=driver_id, vehicle_id=vehicle_id, order_id=order_id)
        )
    return await plans_page(request)


@router.post("/locations", response_class=HTMLResponse)
async def add_location(
    request: Request,
    zip: str = Form(...),
    city: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
):
    with get_db() as con:
        location_service.create_location(
            con,
            location_schemas.LocationCreate(
                zip=zip, city=city, latitude=latitude, longitude=longitude
            )
        )
    return await locations_page(request)


@router.post("/drivers", response_class=HTMLResponse)
async def add_driver(
    request: Request,
    driver_id: str = Form(...),
    location_id: int = Form(...),
    skill_adr: str | None = Form(None),
    skill_ehbo: str | None = Form(None),
):
    with get_db() as con:
        driver_service.create_driver(
            con,
            driver_schemas.DriverCreate(
                driver_id=driver_id, location_id=location_id, skill_adr=_bool(skill_adr), skill_ehbo=_bool(skill_ehbo)
            )
        )
    return await drivers_page(request)


@router.delete("/drivers/{driver_id}", response_class=HTMLResponse)
async def deactivate_driver(driver_id: str, request: Request):
    with get_db() as con:
        driver_service.delete_driver(con, driver_id)
    return await drivers_page(request)


@router.get("/vehicles", response_class=HTMLResponse)
async def vehicles_page(request: Request):
    with get_db() as con:
        vehicles = vehicle_service.list_vehicles(con, include_inactive=True)
    locations = {location["location_id"]: location["address"] for location in _locations_context()}
    rows = [
        (vehicle.vehicle_id, vehicle.license_plate, vehicle.location_id,
         vehicle.is_active, vehicle.spec_liftgate, vehicle.spec_refrigerated,
         locations.get(vehicle.location_id, "Unknown"), getattr(vehicle, "vehicle_index", 0))
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
    with get_db() as con:
        vehicle_service.create_vehicle(
            con,
            vehicle_schemas.VehicleCreate(
                vehicle_id=vehicle_id, license_plate=license_plate, location_id=location_id,
                spec_liftgate=_bool(spec_liftgate), spec_refrigerated=_bool(spec_refrigerated)
            )
        )
    return await vehicles_page(request)


@router.delete("/vehicles/{vehicle_id}", response_class=HTMLResponse)
async def deactivate_vehicle(vehicle_id: str, request: Request):
    with get_db() as con:
        vehicle_service.delete_vehicle(con, vehicle_id)
    return await vehicles_page(request)


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request):
    with get_db() as con:
        orders = order_service.list_orders(con)
    locations = {location["location_id"]: location["address"] for location in _locations_context()}
    rows = [
        (order.order_id, order.destination_location_id, order.req_driver_adr,
         order.req_driver_ehbo, order.req_vehicle_liftgate,
         order.req_vehicle_refrigerated,
         locations.get(order.destination_location_id, "Unknown"), getattr(order, "order_index", 0))
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
    with get_db() as con:
        order_service.create_order(
            con,
            order_schemas.OrderCreate(
                order_id=order_id, destination_location_id=destination_location_id,
                req_driver_adr=_bool(req_driver_adr), req_driver_ehbo=_bool(req_driver_ehbo),
                req_vehicle_liftgate=_bool(req_vehicle_liftgate), req_vehicle_refrigerated=_bool(req_vehicle_refrigerated)
            )
        )
    return await orders_page(request)


@router.post("/match", response_class=HTMLResponse)
async def run_match(request: Request):
    results = [r.model_dump() for r in matching_engine.run_corematch_logistics(DB_PATH)]
    return _tmpl(request, "partials/match_results.html", {"results": results})


@router.post("/seed", response_class=HTMLResponse)
async def seed_demo(request: Request):
    from engine.matching import _seed_demo
    with get_db() as con:
        if con.execute("SELECT COUNT(*) FROM drivers").fetchone()[0] == 0:
            _seed_demo(con)
    return HTMLResponse("<p class=\"text-green-600 font-semibold\">Demo data seeded ✓</p>")

