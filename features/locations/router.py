import duckdb
from fastapi import APIRouter, Depends, HTTPException
from core.database import get_db
from features.locations.schemas import Location, LocationCreate, DistanceMatrixItem
from features.locations.service import location_service

router = APIRouter(prefix="/api", tags=["locations"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("/locations", response_model=list[Location])
async def list_locations_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return location_service.list_locations(con=con)

@router.post("/locations", response_model=Location)
async def create_location_api(payload: LocationCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return location_service.create_location(payload, con=con)

@router.get("/distance-matrix/{origin_zip}", response_model=list[DistanceMatrixItem])
async def distance_matrix_api(origin_zip: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    rows = location_service.get_distance_matrix(origin_zip, con=con)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Location not found: {origin_zip}")
    return list(rows)



