# CoreMatch-Logistics: Pydantic & Vertical Slice Architecture Migration Spec

- **Date:** 2026-09-11
- **Status:** Approved
- **Scope:** Full end-to-end domain migration to Pydantic v2 and Vertical Slice Architecture (no backward-compatibility shims).

---

## 1. Overview & Objectives

CoreMatch-Logistics is a dual-resource matching and route planning engine built on DuckDB, Pyroaring bitmaps, FastAPI, and FastMCP. The application previously used untyped dictionaries (`dict = Body(...)`) across API endpoints and concentrated all business logic into a single 558-line file (`services/resources.py`) and all REST endpoints in `api/routes.py`.

This migration achieves two goals:
1. **End-to-End Pydantic v2 Models**: Formalize all domain schemas, request validations, and response models with Pydantic v2.
2. **Vertical Slice Architecture**: Decompose the codebase by business capability (`features/locations`, `features/drivers`, `features/vehicles`, `features/orders`, `features/matching`, `features/plans`), co-locating schemas, database queries/service logic, and API endpoints.

Because this repository is a standalone application without external package consumers, no backward-compatibility facade shims will be retained. Old monolithic files (`services/resources.py`, `api/routes.py`) will be completely replaced.

---

## 2. Directory Structure

```text
corematch-logistics/
├── core/
│   ├── __init__.py
│   ├── config.py           # Paths and environment configuration
│   ├── database.py         # DuckDB connections, transactions & typed model query helpers
│   └── models.py           # CoreMatchBaseModel with Pydantic ConfigDict
├── features/
│   ├── __init__.py
│   ├── locations/
│   │   ├── __init__.py
│   │   ├── schemas.py      # Location, LocationCreate, DistanceMatrixItem
│   │   ├── service.py      # Location CRUD & Haversine distance matrix computation
│   │   └── router.py       # /api/locations & /api/distance-matrix endpoints
│   ├── drivers/
│   │   ├── __init__.py
│   │   ├── schemas.py      # Driver, DriverCreate, DriverUpdate
│   │   ├── service.py      # Driver queries, active toggle, skills
│   │   └── router.py       # /api/drivers endpoints
│   ├── vehicles/
│   │   ├── __init__.py
│   │   ├── schemas.py      # Vehicle, VehicleCreate, VehicleUpdate
│   │   ├── service.py      # Vehicle queries, active toggle, specs
│   │   └── router.py       # /api/vehicles endpoints
│   ├── orders/
│   │   ├── __init__.py
│   │   ├── schemas.py      # Order, OrderCreate, OrderUpdate
│   │   ├── service.py      # Order CRUD & requirement flags
│   │   └── router.py       # /api/orders endpoints
│   ├── matching/
│   │   ├── __init__.py
│   │   ├── schemas.py      # MatchResult, MatchStatus
│   │   ├── engine.py       # Pyroaring bitmap dual-resource matching engine
│   │   └── router.py       # /api/match endpoint
│   └── plans/
│       ├── __init__.py
│       ├── schemas.py      # Plan, PlanDetail, PlanOrderAdd, PlanRouteSwitch, PlanOrderMove,
│       │                   # StopEvaluation, RouteEvaluation, PlanValidationResult
│       ├── service.py      # Plan generation, stop reordering, validation, route evaluation
│       └── router.py       # /api/plans endpoints
├── mcp_tools/
│   ├── __init__.py
│   └── server.py           # FastMCP server tools calling feature services directly
├── ui/
│   ├── routes.py           # HTMX views calling feature services directly
│   └── templates/          # Jinja2 templates (consuming Pydantic models / dicts)
├── app.py                  # Main FastAPI app mounting feature routers & UI
└── tests/
    ├── test_engine.py      # Engine and matching tests (fixtures updated for schema)
    └── test_api.py         # API tests with schema validation checks
```

---

## 3. Core Layer Specifications

### 3.1 `core/models.py`
All models inherit from `CoreMatchBaseModel`:
```python
from pydantic import BaseModel, ConfigDict

class CoreMatchBaseModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )
```

### 3.2 `core/database.py`
Provides typed query utilities:
- `get_db() -> ContextManager[duckdb.DuckDBPyConnection]`
- `init_schema(con)`
- `query_models(model_cls: type[T], con, sql: str, params: list = None) -> list[T]`
- `query_model_or_none(model_cls: type[T], con, sql: str, params: list = None) -> T | None`
- `execute_update(con, table: str, key_col: str, key_val: Any, data: BaseModel | dict) -> dict[str, Any]`

---

## 4. Feature Slices Specifications

### 4.1 Locations (`features/locations`)
- **Schemas**:
  - `LocationBase`: `zip: str`, `city: str`, `latitude: float`, `longitude: float`
  - `LocationCreate(LocationBase)`: Payload for new location.
  - `Location(LocationBase)`: Adds `location_id: int`.
  - `DistanceMatrixItem`: `dest_zip: str`, `distance_m: int`, `travel_time_min: int`.
- **Endpoints**:
  - `GET /api/locations -> list[Location]`
  - `POST /api/locations (LocationCreate) -> Location`
  - `GET /api/distance-matrix/{origin_zip} -> list[DistanceMatrixItem]`

### 4.2 Drivers (`features/drivers`)
- **Schemas**:
  - `DriverBase`: `driver_id: str`, `location_id: int`, `skill_adr: bool = False`, `skill_ehbo: bool = False`
  - `DriverCreate(DriverBase)`
  - `DriverUpdate`: `location_id: int | None = None`, `is_active: bool | None = None`, `skill_adr: bool | None = None`, `skill_ehbo: bool | None = None`
  - `Driver(DriverBase)`: Adds `driver_index: int`, `is_active: bool = True`.
- **Endpoints**:
  - `GET /api/drivers?include_inactive=bool -> list[Driver]`
  - `POST /api/drivers (DriverCreate) -> Driver`
  - `PATCH /api/drivers/{driver_id} (DriverUpdate) -> Driver`
  - `DELETE /api/drivers/{driver_id} -> Driver` (soft delete `is_active=False`)

### 4.3 Vehicles (`features/vehicles`)
- **Schemas**:
  - `VehicleBase`: `vehicle_id: str`, `license_plate: str`, `location_id: int`, `spec_liftgate: bool = False`, `spec_refrigerated: bool = False`
  - `VehicleCreate(VehicleBase)`
  - `VehicleUpdate`: `license_plate: str | None = None`, `location_id: int | None = None`, `is_active: bool | None = None`, `spec_liftgate: bool | None = None`, `spec_refrigerated: bool | None = None`
  - `Vehicle(VehicleBase)`: Adds `vehicle_index: int`, `is_active: bool = True`.
- **Endpoints**:
  - `GET /api/vehicles?include_inactive=bool -> list[Vehicle]`
  - `POST /api/vehicles (VehicleCreate) -> Vehicle`
  - `PATCH /api/vehicles/{vehicle_id} (VehicleUpdate) -> Vehicle`
  - `DELETE /api/vehicles/{vehicle_id} -> Vehicle` (soft delete `is_active=False`)

### 4.4 Orders (`features/orders`)
- **Schemas**:
  - `OrderBase`: `order_id: str`, `destination_location_id: int`, `req_driver_adr: bool = False`, `req_driver_ehbo: bool = False`, `req_vehicle_liftgate: bool = False`, `req_vehicle_refrigerated: bool = False`
  - `OrderCreate(OrderBase)`
  - `OrderUpdate`: `destination_location_id: int | None = None`, `req_driver_adr: bool | None = None`, `req_driver_ehbo: bool | None = None`, `req_vehicle_liftgate: bool | None = None`, `req_vehicle_refrigerated: bool | None = None`
  - `Order(OrderBase)`
- **Endpoints**:
  - `GET /api/orders -> list[Order]`
  - `POST /api/orders (OrderCreate) -> Order`
  - `PATCH /api/orders/{order_id} (OrderUpdate) -> Order`
  - `DELETE /api/orders/{order_id} -> Order`

### 4.5 Matching Engine (`features/matching`)
- **Schemas**:
  - `MatchResult`: `order_id: str`, `assigned_driver: str | None`, `assigned_vehicle: str | None`, `status: str`
- **Engine Logic**:
  - Pyroaring BitMap indexing across active drivers/vehicles, distance compatibility matrices, and skill/spec constraints.
  - Returns `list[MatchResult]`.
- **Endpoints**:
  - `POST /api/match -> list[MatchResult]`

### 4.6 Plans (`features/plans`)
- **Schemas**:
  - `Plan`: `plan_id: str`, `name: str`
  - `PlanCreate`: `plan_id: str`, `name: str`
  - `PlanOrderAssignment`: `plan_id: str`, `order_id: str`, `driver_id: str | None`, `vehicle_id: str | None`, `stop_sequence: int`
  - `PlanOrderAdd`: `order_id: str`, `driver_id: str`, `vehicle_id: str`, `stop_sequence: int = 0`
  - `PlanRouteSwitch`: `current_driver_id: str`, `current_vehicle_id: str`, `driver_id: str`, `vehicle_id: str`
  - `PlanOrderMove`: `driver_id: str`, `vehicle_id: str`, `direction: Literal[-1, 1]`
  - `StopEvaluation`: `plan_id: str`, `order_id: str`, `driver_id: str`, `vehicle_id: str`, `stop_sequence: int`, `origin_zip: str`, `destination_zip: str`, `driving_time_min: int`, `departure_time: str`, `arrival_time: str`
  - `RouteEvaluation`: `plan_id: str`, `driver_id: str`, `vehicle_id: str`, `start_zip: str`, `last_stop_zip: str`, `return_driving_time_min: int`, `return_departure_time: str`, `return_arrival_time: str`
  - `PlanOrderStop`: Combines `PlanOrderAssignment` with optional embedded `evaluation: StopEvaluation | None`
  - `PlanRouteGroup`: `driver_id: str`, `vehicle_id: str`, `stops: list[PlanOrderStop]`, `return_: RouteEvaluation | None`
  - `PlanValidationResult`: `plan_id: str`, `valid: bool`, `errors: list[str]`
  - `PlanDetail`: `plan_id: str`, `name: str`, `orders: list[PlanOrderAssignment]`, `orders_by_driver: dict[str, list[PlanOrderAssignment]]`, `orders_by_vehicle: dict[str, list[PlanOrderAssignment]]`, `evaluation: list[StopEvaluation]`, `route_evaluation: list[RouteEvaluation]`, `route_groups: list[PlanRouteGroup]`
- **Endpoints**:
  - `GET /api/plans -> list[Plan]`
  - `POST /api/plans (PlanCreate) -> Plan`
  - `GET /api/plans/{plan_id} -> PlanDetail`
  - `POST /api/plans/{plan_id}/orders (PlanOrderAdd) -> PlanDetail`
  - `POST /api/plans/{plan_id}/match -> PlanDetail`
  - `POST /api/plans/{plan_id}/evaluate -> PlanDetail`
  - `POST /api/plans/{plan_id}/validate -> PlanValidationResult`
  - `PATCH /api/plans/{plan_id}/routes (PlanRouteSwitch) -> PlanDetail`
  - `POST /api/plans/{plan_id}/orders/{order_id}/move (PlanOrderMove) -> PlanDetail`

---

## 5. MCP Tools & UI Integration

1. **FastMCP Server (`mcp_tools/server.py`)**:
   - Directly calls slice services (`features.drivers.service`, `features.plans.service`, etc.).
   - FastMCP tool inputs and return values are typed with Pydantic models.
2. **UI (`ui/routes.py`)**:
   - Handlers call slice services directly.
   - Pydantic models or `.model_dump()` dictionaries are supplied to Jinja2 templates, ensuring complete rendering compatibility.

---

## 6. Testing & Quality Assurance

1. **Dependencies (`pyproject.toml`)**:
   - Explicitly add `pydantic>=2.10.0` to dependencies.
2. **Fix `test_engine.py`**:
   - Update `_make_db` helper to use current table schemas (`locations`, `location_id`, `destination_location_id`) so all 14 tests pass.
3. **API & Validation Tests**:
   - Update existing tests to use new slice routers.
   - Add negative tests asserting 422 HTTP errors for invalid payloads (e.g., negative move directions, missing required fields).
