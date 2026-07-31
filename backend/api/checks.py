"""장부 정합성 점검 REST API.

조회 전용이며 어긋난 값을 자동으로 고치지 않는다.
"""

from fastapi import APIRouter

from api.models import LedgerConsistencyResponse
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/checks",
    tags=["checks"],
)


@router.get(
    "/ledger-consistency",
    response_model=LedgerConsistencyResponse,
    operation_id="check_ledger_consistency",
    summary="보유 수강권 잔여 횟수 정합성 점검",
    description=(
        "각 보유 수강권의 저장된 잔여 횟수와 "
        "total_sessions + SUM(attendance_records.session_delta) 를 "
        "비교한다. 현재 그 수강권을 가리키는 수강 기록만 계산하므로 "
        "수강 기록의 연결이 끊긴 경우 차이가 남을 수 있다. "
        "items에는 값이 어긋난 수강권만 담기며 자동 수정은 하지 않는다."
    ),
)
def check_ledger_consistency(academy_id: int) -> dict:
    return db_connector.check_ledger_consistency(academy_id)
