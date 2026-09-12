from typing import Generator, Sequence
from core.base_service import BaseService
from core.database import get_db
from features.matching.schemas import MatchResult
from features.matching.engine import run_corematch_logistics


class MatchingService(BaseService):
    """Domain service for logistics matching."""

    def match(self) -> Sequence[MatchResult]:
        with self.con() as con:
            return run_corematch_logistics(con)


def get_matching_service() -> Generator[MatchingService, None, None]:
    with get_db() as con:
        yield MatchingService(con)


matching_service = MatchingService()

match = matching_service.match