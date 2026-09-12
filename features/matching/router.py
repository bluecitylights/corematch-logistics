from fastapi import APIRouter
from features.matching.schemas import MatchResult
from features.matching import engine
from core.config import DB_PATH

router = APIRouter(prefix="/api/match", tags=["matching"])

@router.post("", response_model=list[MatchResult])
async def api_run_matching():
    # Matching engine opens its own connection for pure pandas analytical speed
    return engine.run_corematch_logistics(DB_PATH)

