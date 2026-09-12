import duckdb
from fastapi import APIRouter, Depends, HTTPException
from core.database import get_db
from features.plans.schemas import Plan, PlanCreate, PlanDetail, PlanOrderAdd, PlanRouteSwitch, PlanValidationResult
from features.plans.service import plan_service

router = APIRouter(prefix="/api/plans", tags=["plans"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("", response_model=list[Plan])
async def list_plans_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return plan_service.list_plans(con=con)

@router.post("", response_model=Plan)
async def create_plan_api(payload: PlanCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return plan_service.create_plan(payload, con=con)

@router.get("/{plan_id}", response_model=PlanDetail)
async def get_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    plan = plan_service.get_plan(plan_id, con=con)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
    return plan

@router.post("/{plan_id}/orders", response_model=PlanDetail)
async def add_plan_order_api(plan_id: str, payload: PlanOrderAdd, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return plan_service.add_plan_order(plan_id, payload, con=con)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/routes/{driver_id}/{vehicle_id}/switch", response_model=PlanDetail)
async def switch_plan_route_api(plan_id: str, driver_id: str, vehicle_id: str, payload: PlanRouteSwitch, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return plan_service.switch_plan_route(plan_id, driver_id, vehicle_id, payload, con=con)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/routes/{driver_id}/{vehicle_id}/orders/{order_id}/move", response_model=PlanDetail)
async def move_plan_order_api(plan_id: str, driver_id: str, vehicle_id: str, order_id: str, direction: int, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return plan_service.move_plan_order(plan_id, driver_id, vehicle_id, order_id, direction, con=con)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/generate", response_model=PlanDetail)
async def generate_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return plan_service.generate_plan(plan_id, con=con)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/evaluate", response_model=PlanDetail)
async def evaluate_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return plan_service.evaluate_plan(plan_id, con=con)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/validate", response_model=PlanValidationResult)
async def validate_plan_api(plan_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    try:
        return plan_service.validate_plan(plan_id, con=con)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



