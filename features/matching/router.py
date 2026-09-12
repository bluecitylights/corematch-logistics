from fastapi import APIRouter, Depends
from features.matching.schemas import MatchResult
from features.matching.service import MatchingService, get_matching_service

router = APIRouter(prefix="/api/match", tags=["matching"])


@router.post("", response_model=list[MatchResult])
async def api_run_matching(service: MatchingService = Depends(get_matching_service)):
    return service.match()
