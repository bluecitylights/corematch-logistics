from fastapi import APIRouter

from features.locations.router import router as locations_router
from features.drivers.router import router as drivers_router
from features.vehicles.router import router as vehicles_router
from features.orders.router import router as orders_router
from features.plans.router import router as plans_router
from features.matching.router import router as matching_router

api_router = APIRouter()

api_router.include_router(locations_router)
api_router.include_router(drivers_router)
api_router.include_router(vehicles_router)
api_router.include_router(orders_router)
api_router.include_router(plans_router)
api_router.include_router(matching_router)

