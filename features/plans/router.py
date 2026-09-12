from fastapi import APIRouter, Depends, HTTPException
import duckdb

from core.database import get_db
from features.plans.schemas import Plan, PlanCreate, PlanDetail, PlanOrderAdd, PlanRouteSwitch, PlanValidationResult
from features.plans import service

router = APIRouter(prefix="/api/plans", tags=["plans"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("", response_model=list[Plan])
async def list_plans_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.list_plans(con)

@router.post("", response_model=Plan)
async def create_plan_api(payload: PlanCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.create_plan(con, payload)

@router.get("/{plan_id}", response_model=PlanDetail)
async def get_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    plan = service.get_plan(con, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
    return plan

@router.post("/{plan_id}/orders", response_model=PlanDetail)
async def add_plan_order_api(plan_id: str, payload: PlanOrderAdd, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return service.add_plan_order(con, plan_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/routes/{driver_id}/{vehicle_id}/switch", response_model=PlanDetail)
async def switch_plan_route_api(plan_id: str, driver_id: str, vehicle_id: str, payload: PlanRouteSwitch, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return service.switch_plan_route(con, plan_id, driver_id, vehicle_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/routes/{driver_id}/{vehicle_id}/orders/{order_id}/move", response_model=PlanDetail)
async def move_plan_order_api(plan_id: str, driver_id: str, vehicle_id: str, order_id: str, direction: int, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return service.move_plan_order(con, plan_id, driver_id, vehicle_id, order_id, direction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/generate", response_model=PlanDetail)
async def generate_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return service.generate_plan(con, plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/evaluate", response_model=PlanDetail)
async def evaluate_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return service.evaluate_plan(con, plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/validate", response_model=PlanValidationResult)
async def validate_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return service.validate_plan(con, plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

