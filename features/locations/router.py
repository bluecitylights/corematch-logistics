from fastapi import APIRouter, Depends, HTTPException
from typing import Sequence
import duckdb

from core.database import get_db
from features.locations.schemas import Location, LocationCreate, DistanceMatrixItem
from features.locations import service

router = APIRouter(prefix="/api", tags=["locations"])

# We define dependency to yield con to match FastAPIs style
def get_db_con():
    with get_db() as con:
        yield con

@router.get("/locations", response_model=list[Location])
async def list_locations_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.list_locations(con)

@router.post("/locations", response_model=Location)
async def create_location_api(payload: LocationCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.create_location(con, payload)

@router.get("/distance-matrix/{origin_zip}", response_model=list[DistanceMatrixItem])
async def distance_matrix_api(origin_zip: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    rows = service.get_distance_matrix(con, origin_zip)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Location not found: {origin_zip}")
    return list(rows)

