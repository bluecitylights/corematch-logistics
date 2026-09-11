# Pydantic & Vertical Slice Architecture Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate CoreMatch-Logistics completely to Pydantic v2 domain schemas and a clean Vertical Slice Architecture (`features/`), replacing the monolithic service and API files without backward-compatibility shims.

**Architecture:** Each domain capability (`locations`, `drivers`, `vehicles`, `orders`, `matching`, `plans`) becomes a self-contained vertical slice in `features/<domain>/` containing its own `schemas.py`, `service.py`, and `router.py`. Core database mapping and base model utilities live in `core/`. Callers (`ui/routes.py`, `mcp_tools/server.py`, `app.py`) import directly from the slices.

**Tech Stack:** Python 3.13+, FastAPI, Pydantic v2, DuckDB, Pyroaring, Jinja2, Pytest, UV.

## Global Constraints
- Pydantic v2 floor: `pydantic>=2.10.0`
- All models inherit from `core.models.CoreMatchBaseModel` with `extra="forbid"` and `from_attributes=True`.
- No backward-compatibility shims or facades: delete `services/resources.py` and old `api/routes.py`.
- Preserve existing REST API contract routes and behavior so UI and external clients function seamlessly.
- All tests must pass cleanly under `uv run pytest`.

---

### Task 1: Dependency Setup & Baseline Test Fixture Fix

**Files:**
- Modify: `pyproject.toml`
- Modify: `test_engine.py:20-65`

**Interfaces:**
- Produces: Updated schema seeding in `test_engine.py` compatible with `locations`, `location_id`, and `destination_location_id`.

- [ ] **Step 1: Update `pyproject.toml` with explicit `pydantic` dependency**

Add `pydantic>=2.10.0` to `dependencies` in `pyproject.toml`:
```toml
dependencies = [
    "duckdb>=1.5.5",
    "fastapi>=0.141.1",
    "fastmcp>=2.12.0",
    "httpx>=0.28.1",
    "jinja2>=3.1.6",
    "pandas>=3.0.5",
    "pydantic>=2.10.0",
    "pyroaring>=1.1.0",
    "python-multipart>=0.0.32",
    "uvicorn[standard]>=0.52.4",
]
```

- [ ] **Step 2: Sync dependencies with uv**

Run: `uv sync`
Expected: Dependencies locked and synced successfully.

- [ ] **Step 3: Update `test_engine.py` database fixture helper**

Fix `_make_db` in `test_engine.py` to seed `locations` and use `location_id` and `destination_location_id`:
```python
def _make_db(drivers=None, vehicles=None, orders=None) -> str:
    import uuid
    db_path = str(Path(__file__).parent / f"_test_{uuid.uuid4().hex}.duckdb")
    con = duckdb.connect(db_path)
    init_schema(con)

    con.execute(
        "INSERT INTO locations (location_id, zip, city, latitude, longitude) "
        "VALUES (1, '1000AA', 'CityA', 52.37, 4.89), "
        "       (2, '2000BB', 'CityB', 52.38, 4.90), "
        "       (3, '3000CC', 'Metro', 52.39, 4.91), "
        "       (4, '4000DD', 'Nowhere', 52.00, 4.00)"
    )
    con.execute(
        "INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min) "
        "VALUES ('1000AA', '2000BB', 5000, 10), "
        "       ('2000BB', '1000AA', 5000, 10), "
        "       ('3000CC', '3000CC', 0, 0), "
        "       ('1000AA', '1000AA', 0, 0), "
        "       ('2000BB', '2000BB', 0, 0)"
    )

    if drivers:
        con.executemany(
            "INSERT INTO drivers "
            "(driver_id, location_id, is_active, skill_adr, skill_ehbo) "
            "VALUES (?, ?, ?, ?, ?)",
            drivers,
        )
    if vehicles:
        con.executemany(
            "INSERT INTO vehicles "
            "(vehicle_id, license_plate, location_id, is_active, "
            "spec_liftgate, spec_refrigerated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            vehicles,
        )
    if orders:
        con.executemany(
            "INSERT INTO orders "
            "(order_id, destination_location_id, req_driver_adr, req_driver_ehbo, "
            "req_vehicle_liftgate, req_vehicle_refrigerated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            orders,
        )
    con.close()
    return db_path
```
Also update driver, vehicle, and order tuples in `test_engine.py` to use integer `location_id` (e.g. `2` for CityB, `3` for Metro, `4` for Nowhere) instead of city strings.

- [ ] **Step 4: Run pytest on test_engine.py**

Run: `uv run pytest test_engine.py -v`
Expected: All 14 tests in `test_engine.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock test_engine.py
git commit -m "fix: update test_engine fixtures and add pydantic dependency"
```

---

### Task 2: Core Foundation (`core/`)

**Files:**
- Create: `core/__init__.py`
- Create: `core/config.py`
- Create: `core/models.py`
- Create: `core/database.py`
- Create: `tests/test_core.py`

**Interfaces:**
- Produces:
  - `CoreMatchBaseModel` in `core.models`
  - `get_db()`, `query_models()`, `query_model_or_none()`, `execute_update()`, `api_rows()` in `core.database`
  - `DB_PATH` in `core.config`

- [ ] **Step 1: Write tests for core models and database helpers**

Create `tests/test_core.py`:
```python
import duckdb
import pytest
from pydantic import ValidationError
from core.models import CoreMatchBaseModel
from core.database import query_models, query_model_or_none, execute_update, init_schema

class DummyModel(CoreMatchBaseModel):
    id: int
    name: str

def test_base_model_rejects_extra_fields():
    with pytest.raises(ValidationError):
        DummyModel(id=1, name="Test", extra_prop=123)

def test_query_models_maps_rows(tmp_path):
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    con.execute("CREATE TABLE dummy (id INT, name VARCHAR)")
    con.execute("INSERT INTO dummy VALUES (1, 'Alice'), (2, 'Bob')")
    
    results = query_models(DummyModel, con, "SELECT * FROM dummy ORDER BY id")
    assert len(results) == 2
    assert results[0].name == "Alice"
    assert results[1].id == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'core')

- [ ] **Step 3: Implement `core/config.py`, `core/models.py`, `core/database.py`**

Create `core/config.py`:
```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("COREMATCH_DB_PATH", str(BASE_DIR / "corematch.duckdb"))
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
```

Create `core/models.py`:
```python
from pydantic import BaseModel, ConfigDict

class CoreMatchBaseModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        extra="forbid",
    )
```

Create `core/database.py`:
```python
from contextlib import contextmanager
from typing import Any, TypeVar
import duckdb
from pydantic import BaseModel
from core.config import DB_PATH, SCHEMA_PATH

T = TypeVar("T", bound=BaseModel)

@contextmanager
def get_db(db_path: str = DB_PATH):
    con = duckdb.connect(db_path)
    try:
        yield con
    finally:
        con.close()

def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(SCHEMA_PATH.read_text())

def api_rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    cursor = con.execute(sql, params or [])
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def query_models(model_cls: type[T], con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> list[T]:
    rows = api_rows(con, sql, params)
    return [model_cls.model_validate(row) for row in rows]

def query_model_or_none(model_cls: type[T], con: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> T | None:
    models = query_models(model_cls, con, sql, params)
    return models[0] if models else None

def execute_update(table: str, key_col: str, key_val: Any, fields: dict[str, Any], con: duckdb.DuckDBPyConnection | None = None) -> dict[str, Any]:
    if not fields:
        raise ValueError("No fields to update")
    set_clause = ", ".join(f"{key} = ?" for key in fields)
    params = list(fields.values()) + [key_val]
    
    def _run(c):
        c.execute(f"UPDATE {table} SET {set_clause} WHERE {key_col} = ?", params)
        rows = api_rows(c, f"SELECT * FROM {table} WHERE {key_col} = ?", [key_val])
        if not rows:
            raise KeyError(f"{table} with {key_col}={key_val} not found")
        return rows[0]

    if con is not None:
        return _run(con)
    with get_db() as c:
        return _run(c)
```

Create `core/__init__.py` exporting:
```python
from core.config import DB_PATH
from core.database import get_db, init_schema, api_rows, query_models, query_model_or_none, execute_update
from core.models import CoreMatchBaseModel
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/ tests/test_core.py
git commit -m "feat: add core module with database utilities and pydantic base model"
```

---

### Task 3: Locations Feature Slice (`features/locations`)

**Files:**
- Create: `features/locations/__init__.py`
- Create: `features/locations/schemas.py`
- Create: `features/locations/service.py`
- Create: `features/locations/router.py`
- Create: `tests/features/test_locations.py`

**Interfaces:**
- Produces:
  - Models: `LocationBase`, `LocationCreate`, `Location`, `DistanceMatrixItem`
  - Service: `list_locations()`, `create_location()`, `get_distance_matrix()`, `rebuild_distance_matrix()`
  - Router: `router` with prefix `/api`

- [ ] **Step 1: Write failing tests for Locations slice**

Create `tests/features/test_locations.py` testing model validation, CRUD, distance matrix generation, and API router.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/features/test_locations.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `features/locations/`**

Implement `schemas.py`, `service.py`, and `router.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/features/test_locations.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add features/locations/ tests/features/test_locations.py
git commit -m "feat(locations): implement vertical slice with pydantic models"
```

---

### Task 4: Drivers Feature Slice (`features/drivers`)

**Files:**
- Create: `features/drivers/__init__.py`
- Create: `features/drivers/schemas.py`
- Create: `features/drivers/service.py`
- Create: `features/drivers/router.py`
- Create: `tests/features/test_drivers.py`

**Interfaces:**
- Produces:
  - Models: `DriverBase`, `DriverCreate`, `DriverUpdate`, `Driver`
  - Service: `list_drivers()`, `create_driver()`, `update_driver()`, `delete_driver()`
  - Router: `router` with prefix `/api/drivers`

- [ ] **Step 1: Write failing tests for Drivers slice**

Create `tests/features/test_drivers.py` testing `DriverCreate`, `DriverUpdate`, active toggling, soft delete, and router endpoints with status codes and 422 validations.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/features/test_drivers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `features/drivers/`**

Implement `schemas.py`, `service.py`, and `router.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/features/test_drivers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add features/drivers/ tests/features/test_drivers.py
git commit -m "feat(drivers): implement vertical slice with pydantic models"
```

---

### Task 5: Vehicles Feature Slice (`features/vehicles`)

**Files:**
- Create: `features/vehicles/__init__.py`
- Create: `features/vehicles/schemas.py`
- Create: `features/vehicles/service.py`
- Create: `features/vehicles/router.py`
- Create: `tests/features/test_vehicles.py`

**Interfaces:**
- Produces:
  - Models: `VehicleBase`, `VehicleCreate`, `VehicleUpdate`, `Vehicle`
  - Service: `list_vehicles()`, `create_vehicle()`, `update_vehicle()`, `delete_vehicle()`
  - Router: `router` with prefix `/api/vehicles`

- [ ] **Step 1: Write failing tests for Vehicles slice**

Create `tests/features/test_vehicles.py` testing `VehicleCreate`, `VehicleUpdate`, specs, soft delete, and router endpoints.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/features/test_vehicles.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `features/vehicles/`**

Implement `schemas.py`, `service.py`, and `router.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/features/test_vehicles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add features/vehicles/ tests/features/test_vehicles.py
git commit -m "feat(vehicles): implement vertical slice with pydantic models"
```

---

### Task 6: Orders Feature Slice (`features/orders`)

**Files:**
- Create: `features/orders/__init__.py`
- Create: `features/orders/schemas.py`
- Create: `features/orders/service.py`
- Create: `features/orders/router.py`
- Create: `tests/features/test_orders.py`

**Interfaces:**
- Produces:
  - Models: `OrderBase`, `OrderCreate`, `OrderUpdate`, `Order`
  - Service: `list_orders()`, `create_order()`, `update_order()`, `delete_order()`
  - Router: `router` with prefix `/api/orders`

- [ ] **Step 1: Write failing tests for Orders slice**

Create `tests/features/test_orders.py` testing `OrderCreate`, `OrderUpdate`, `delete_order`, and router endpoints.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/features/test_orders.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `features/orders/`**

Implement `schemas.py`, `service.py`, and `router.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/features/test_orders.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add features/orders/ tests/features/test_orders.py
git commit -m "feat(orders): implement vertical slice with pydantic models"
```

---

### Task 7: Matching Feature Slice (`features/matching`)

**Files:**
- Create: `features/matching/__init__.py`
- Create: `features/matching/schemas.py`
- Create: `features/matching/engine.py`
- Create: `features/matching/router.py`
- Create: `tests/features/test_matching.py`

**Interfaces:**
- Produces:
  - Models: `MatchResult`
  - Engine: `run_corematch_logistics(db_path: str) -> list[MatchResult]` (and DataFrame helper)
  - Router: `POST /api/match -> list[MatchResult]`

- [ ] **Step 1: Write failing tests for Matching slice**

Create `tests/features/test_matching.py` testing `run_corematch_logistics` returning validated `MatchResult` objects and the `/api/match` endpoint.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/features/test_matching.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `features/matching/`**

Move bitmap matching logic from `engine/matching.py` into `features/matching/engine.py`, mapping output rows into `MatchResult` models.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/features/test_matching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add features/matching/ tests/features/test_matching.py
git commit -m "feat(matching): implement vertical slice with pydantic schemas"
```

---

### Task 8: Plans Feature Slice (`features/plans`)

**Files:**
- Create: `features/plans/__init__.py`
- Create: `features/plans/schemas.py`
- Create: `features/plans/service.py`
- Create: `features/plans/router.py`
- Create: `tests/features/test_plans.py`

**Interfaces:**
- Produces:
  - Models: `Plan`, `PlanCreate`, `PlanOrderAssignment`, `PlanOrderAdd`, `PlanRouteSwitch`, `PlanOrderMove`, `StopEvaluation`, `RouteEvaluation`, `PlanOrderStop`, `PlanRouteGroup`, `PlanValidationResult`, `PlanDetail`
  - Service: `list_plans()`, `create_plan()`, `get_plan()`, `add_plan_order()`, `switch_plan_route()`, `move_plan_order()`, `generate_plan()`, `validate_plan()`, `evaluate_plan()`
  - Router: `router` with prefix `/api/plans`

- [ ] **Step 1: Write failing tests for Plans slice**

Create `tests/features/test_plans.py` testing creation, adding orders, route switching, stop move with direction validation, plan evaluation, and plan validation.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/features/test_plans.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `features/plans/`**

Migrate plan logic from `services/resources.py` and evaluation algorithms from `engine/matching.py` into `features/plans/`, utilizing typed Pydantic models throughout.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/features/test_plans.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add features/plans/ tests/features/test_plans.py
git commit -m "feat(plans): implement vertical slice with pydantic models"
```

---

### Task 9: FastMCP Integration

**Files:**
- Modify: `mcp_tools/server.py`
- Create: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: Slice services in `features.locations.service`, `features.drivers.service`, `features.vehicles.service`, `features.orders.service`, `features.plans.service`, `features.matching.engine`

- [ ] **Step 1: Write tests for MCP tools**

Create `tests/test_mcp_server.py` verifying MCP tools execute and return valid serialized data.

- [ ] **Step 2: Update `mcp_tools/server.py`**

Update `mcp_tools/server.py` to import and call feature slice services directly, eliminating untyped dict manipulations.

- [ ] **Step 3: Run pytest on MCP tests**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add mcp_tools/server.py tests/test_mcp_server.py
git commit -m "refactor(mcp): connect fastmcp tools directly to vertical slice services"
```

---

### Task 10: UI Layer & Template Compatibility

**Files:**
- Modify: `ui/routes.py`
- Modify: `test_api.py`

**Interfaces:**
- Consumes: Slice services and models.

- [ ] **Step 1: Update `ui/routes.py`**

Refactor `ui/routes.py` to import directly from `features.*.service` and `features.*.schemas`. Ensure models passed to Jinja2 templates serialize or expose attributes matching existing templates (`.driver_id`, `["driver_id"]`, etc.).

- [ ] **Step 2: Run tests including test_api.py**

Run: `uv run pytest test_api.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add ui/routes.py test_api.py
git commit -m "refactor(ui): update ui routes to use vertical slice services"
```

---

### Task 11: Cleanup & Application Assembly

**Files:**
- Modify: `app.py`
- Delete: `services/resources.py` (and `services/` if empty)
- Delete: `api/routes.py` (and `api/` if empty)
- Delete: `db/locations.py` (moved to `features/locations/service.py`)
- Delete: `engine/matching.py` (moved to `features/matching/` and `features/plans/`)

**Interfaces:**
- `app.py` includes all slice routers:
  - `app.include_router(locations_router)`
  - `app.include_router(drivers_router)`
  - `app.include_router(vehicles_router)`
  - `app.include_router(orders_router)`
  - `app.include_router(matching_router)`
  - `app.include_router(plans_router)`
  - `app.include_router(ui_router)`

- [ ] **Step 1: Update `app.py` to mount all feature routers**

Include all feature routers directly in `app.py`.

- [ ] **Step 2: Remove obsolete monolithic files**

Delete `services/resources.py`, `api/routes.py`, `engine/matching.py`, `db/locations.py`.

- [ ] **Step 3: Run complete pytest suite**

Run: `uv run pytest`
Expected: All tests PASS with zero errors.

- [ ] **Step 4: Commit**

```bash
git add app.py
git rm -r services/ api/ db/locations.py engine/matching.py
git commit -m "chore: remove obsolete monolith files and assemble feature routers in app.py"
```

---

### Task 12: Final End-to-End Verification & Remote Push

**Files:**
- All codebase

- [ ] **Step 1: Run full pytest suite with coverage/verbosity**

Run: `uv run pytest -v`
Expected: 100% passing tests across all test suites.

- [ ] **Step 2: Push branch to origin**

Run: `git push -u origin feat/pydantic-vertical-slices`
Expected: Branch pushed successfully.
