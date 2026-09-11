from core.models import CoreMatchBaseModel
from typing import Any

class PlanCreate(CoreMatchBaseModel):
    plan_id: str
    name: str

class Plan(PlanCreate):
    pass

class PlanOrderAssignment(CoreMatchBaseModel):
    plan_id: str
    order_id: str
    driver_id: str
    vehicle_id: str
    stop_sequence: int

class StopEvaluation(CoreMatchBaseModel):
    order_id: str
    driver_id: str
    vehicle_id: str
    stop_sequence: int
    origin_zip: str
    destination_zip: str
    driving_time_min: int
    departure_time: str
    arrival_time: str

class RouteEvaluation(CoreMatchBaseModel):
    plan_id: str
    driver_id: str
    vehicle_id: str
    start_zip: str
    last_stop_zip: str
    return_driving_time_min: int
    return_departure_time: str
    return_arrival_time: str

class PlanEvaluation(CoreMatchBaseModel):
    stops: list[StopEvaluation]
    routes: list[RouteEvaluation]

class PlanDetail(Plan):
    assignments: list[PlanOrderAssignment]
    evaluation: PlanEvaluation

class PlanOrderAdd(CoreMatchBaseModel):
    order_id: str
    driver_id: str
    vehicle_id: str

class PlanRouteSwitch(CoreMatchBaseModel):
    driver_id: str
    vehicle_id: str

class PlanValidationResult(CoreMatchBaseModel):
    errors: list[str]

