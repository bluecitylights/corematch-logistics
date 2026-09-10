"""FastMCP tools that call the CoreMatch REST API."""

import os
from typing import Any

import httpx
from fastmcp import FastMCP


API_BASE_URL = os.environ.get("COREMATCH_API_URL", "http://127.0.0.1:8000").rstrip("/")
mcp = FastMCP("CoreMatch-Logistics")


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    response = httpx.request(
        method,
        f"{API_BASE_URL}{path}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool
def list_drivers(include_inactive: bool = False) -> list[dict[str, Any]]:
    """List drivers through the CoreMatch REST API."""
    return _request("GET", f"/api/drivers?include_inactive={include_inactive}")


@mcp.tool
def create_driver(driver_id: str, location_id: int, skill_adr: bool = False, skill_ehbo: bool = False) -> dict[str, Any]:
    """Create a driver through the CoreMatch REST API."""
    return _request("POST", "/api/drivers", locals())


@mcp.tool
def update_driver(driver_id: str, location_id: int | None = None, is_active: bool | None = None, skill_adr: bool | None = None, skill_ehbo: bool | None = None) -> dict[str, Any]:
    """Update a driver through the CoreMatch REST API."""
    return _request("PATCH", f"/api/drivers/{driver_id}", {key: value for key, value in locals().items() if key != "driver_id" and value is not None})


@mcp.tool
def delete_driver(driver_id: str) -> dict[str, Any]:
    """Deactivate a driver through the CoreMatch REST API."""
    return _request("DELETE", f"/api/drivers/{driver_id}")


@mcp.tool
def list_vehicles(include_inactive: bool = False) -> list[dict[str, Any]]:
    """List vehicles through the CoreMatch REST API."""
    return _request("GET", f"/api/vehicles?include_inactive={include_inactive}")


@mcp.tool
def create_vehicle(vehicle_id: str, license_plate: str, location_id: int, spec_liftgate: bool = False, spec_refrigerated: bool = False) -> dict[str, Any]:
    """Create a vehicle through the CoreMatch REST API."""
    return _request("POST", "/api/vehicles", locals())


@mcp.tool
def update_vehicle(vehicle_id: str, license_plate: str | None = None, location_id: int | None = None, is_active: bool | None = None, spec_liftgate: bool | None = None, spec_refrigerated: bool | None = None) -> dict[str, Any]:
    """Update a vehicle through the CoreMatch REST API."""
    return _request("PATCH", f"/api/vehicles/{vehicle_id}", {key: value for key, value in locals().items() if key != "vehicle_id" and value is not None})


@mcp.tool
def delete_vehicle(vehicle_id: str) -> dict[str, Any]:
    """Deactivate a vehicle through the CoreMatch REST API."""
    return _request("DELETE", f"/api/vehicles/{vehicle_id}")


@mcp.tool
def list_orders() -> list[dict[str, Any]]:
    """List orders through the CoreMatch REST API."""
    return _request("GET", "/api/orders")


@mcp.tool
def create_order(order_id: str, destination_location_id: int, req_driver_adr: bool = False, req_driver_ehbo: bool = False, req_vehicle_liftgate: bool = False, req_vehicle_refrigerated: bool = False) -> dict[str, Any]:
    """Create an order through the CoreMatch REST API."""
    return _request("POST", "/api/orders", locals())


@mcp.tool
def update_order(order_id: str, destination_location_id: int | None = None, req_driver_adr: bool | None = None, req_driver_ehbo: bool | None = None, req_vehicle_liftgate: bool | None = None, req_vehicle_refrigerated: bool | None = None) -> dict[str, Any]:
    """Update an order through the CoreMatch REST API."""
    return _request("PATCH", f"/api/orders/{order_id}", {key: value for key, value in locals().items() if key != "order_id" and value is not None})


@mcp.tool
def delete_order(order_id: str) -> dict[str, Any]:
    """Delete an order through the CoreMatch REST API."""
    return _request("DELETE", f"/api/orders/{order_id}")


@mcp.tool
def list_plans() -> list[dict[str, Any]]:
    """List plans through the CoreMatch REST API."""
    return _request("GET", "/api/plans")


@mcp.tool
def create_plan(plan_id: str, name: str) -> dict[str, Any]:
    """Create a plan through the CoreMatch REST API."""
    return _request("POST", "/api/plans", {"plan_id": plan_id, "name": name})


@mcp.tool
def get_plan(plan_id: str) -> dict[str, Any]:
    """Get a plan and its order lists grouped by driver and vehicle."""
    return _request("GET", f"/api/plans/{plan_id}")


@mcp.tool
def add_order_to_plan(
    plan_id: str,
    order_id: str,
    driver_id: str,
    vehicle_id: str,
    stop_sequence: int = 0,
) -> dict[str, Any]:
    """Add an order using the plan's single driver-vehicle combination."""
    return _request(
        "POST",
        f"/api/plans/{plan_id}/orders",
        {
            "order_id": order_id,
            "driver_id": driver_id,
            "vehicle_id": vehicle_id,
            "stop_sequence": stop_sequence,
        },
    )


@mcp.tool
def generate_plan(plan_id: str) -> dict[str, Any]:
    """Run matching and generate a plan through the CoreMatch REST API."""
    return _request("POST", f"/api/plans/{plan_id}/match")


@mcp.tool
def run_matching() -> list[dict[str, Any]]:
    """Run matching through the CoreMatch REST API."""
    return _request("POST", "/api/match")


if __name__ == "__main__":
    mcp.run()
