from fastapi import APIRouter, Depends, HTTPException
from features.plans.schemas import Plan, PlanCreate, PlanDetail, PlanOrderAdd, PlanRouteSwitch, PlanValidationResult
from features.plans.service import PlanService, get_plan_service

router = APIRouter(prefix="/api/plans", tags=["plans"])

@router.get("", response_model=list[Plan])
async def list_plans_api(service: PlanService = Depends(get_plan_service)):
    return service.list_plans()

@router.post("", response_model=Plan)
async def create_plan_api(payload: PlanCreate, service: PlanService = Depends(get_plan_service)):
    return service.create_plan(payload)

@router.get("/{plan_id}", response_model=PlanDetail)
async def get_plan_api(plan_id: str, service: PlanService = Depends(get_plan_service)):
    plan = service.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan not found: {plan_id}")
    return plan

@router.post("/{plan_id}/orders", response_model=PlanDetail)
async def add_plan_order_api(plan_id: str, payload: PlanOrderAdd, service: PlanService = Depends(get_plan_service)):
    try:
        return service.add_plan_order(plan_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/routes/{driver_id}/{vehicle_id}/switch", response_model=PlanDetail)
async def switch_plan_route_api(plan_id: str, driver_id: str, vehicle_id: str, payload: PlanRouteSwitch, service: PlanService = Depends(get_plan_service)):
    try:
        return service.switch_plan_route(plan_id, driver_id, vehicle_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/routes/{driver_id}/{vehicle_id}/orders/{order_id}/move", response_model=PlanDetail)
async def move_plan_order_api(plan_id: str, driver_id: str, vehicle_id: str, order_id: str, direction: int, service: PlanService = Depends(get_plan_service)):
    try:
        return service.move_plan_order(plan_id, driver_id, vehicle_id, order_id, direction)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/generate", response_model=PlanDetail)
async def generate_plan_api(plan_id: str, service: PlanService = Depends(get_plan_service)):
    try:
        return service.generate_plan(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/evaluate", response_model=PlanDetail)
async def evaluate_plan_api(plan_id: str, service: PlanService = Depends(get_plan_service)):
    try:
        return service.evaluate_plan(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{plan_id}/validate", response_model=PlanValidationResult)
async def validate_plan_api(plan_id: str, service: PlanService = Depends(get_plan_service)):
    try:
        return service.validate_plan(plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
