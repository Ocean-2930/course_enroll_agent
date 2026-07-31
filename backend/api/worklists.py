"""운영 관리 대상(할 일) 목록 조회 REST API.

조회 전용이다. 상태 변경은 기존 수강 기록 액션 API를 사용한다.
"""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from api.common import Limit, Offset, Order
from api.models import (
    ExpiringPassItem,
    LowBalancePassItem,
    Page,
    PendingAttendanceItem,
    ReregistrationCandidatesResponse,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/worklists",
    tags=["worklists"],
)

ExpiringDays = Annotated[int, Query(ge=0, le=365)]
MaxRemaining = Annotated[int, Query(ge=0)]
RecentDays = Annotated[int, Query(ge=1, le=365)]


def _iso(value: datetime | None) -> str | None:
    return (
        value.replace(microsecond=0).isoformat()
        if value is not None
        else None
    )


@router.get(
    "/pending-attendance",
    response_model=Page[PendingAttendanceItem],
    operation_id="list_pending_attendance",
    summary="과거 미처리 예약 조회",
    description=(
        "예정 시각이 지났는데 아직 RESERVED 상태인 예약을 조회한다. "
        "현재 스키마에는 결석 상태가 없으므로 결석 확정이 아니라 "
        "출결 확인이 필요한 미처리 예약으로만 해석한다. "
        "scheduled_before를 생략하면 현재 시각을 기준으로 한다."
    ),
)
def list_pending_attendance(
    academy_id: int,
    scheduled_before: datetime | None = None,
    scheduled_from: datetime | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "scheduled_at",
        "id",
        "student_name",
        "class_name",
    ] = "scheduled_at",
    order: Order = "asc",
) -> dict:
    return db_connector.list_pending_attendance(
        academy_id,
        scheduled_before=_iso(scheduled_before),
        scheduled_from=_iso(scheduled_from),
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get(
    "/expiring-passes",
    response_model=Page[ExpiringPassItem],
    operation_id="list_expiring_passes",
    summary="만료 예정 수강권 조회",
    description=(
        "오늘부터 days일 이내에 만료되는 보유 수강권을 조회한다. "
        "include_expired=true이면 이미 만료된 수강권도 포함한다. "
        "remaining_only=true이면 잔여 1회 이상만 포함한다. "
        "expired_only=true이면 이미 만료된 수강권만 조회하며, "
        "remaining_only와 함께 쓰면 '만료됐지만 잔여 횟수가 남은' "
        "수강권 목록이 된다. "
        "days_left는 오늘 기준 남은 일수이며 만료된 수강권은 음수다."
    ),
)
def list_expiring_passes(
    academy_id: int,
    days: ExpiringDays = 14,
    include_expired: bool = False,
    remaining_only: bool = True,
    expired_only: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "expire_date",
        "remaining_sessions",
        "student_name",
        "id",
    ] = "expire_date",
    order: Order = "asc",
) -> dict:
    return db_connector.list_expiring_passes(
        academy_id,
        days=days,
        include_expired=include_expired,
        remaining_only=remaining_only,
        expired_only=expired_only,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get(
    "/low-balance-passes",
    response_model=Page[LowBalancePassItem],
    operation_id="list_low_balance_passes",
    summary="잔여 횟수 부족 수강권 조회",
    description=(
        "잔여 횟수가 max_remaining 이하인 보유 수강권을 조회한다. "
        "available_only=true이면 아직 만료되지 않은 수강권만 포함하며 "
        "잔여 0회도 포함한다. 만료된 수강권까지 보려면 false로 둔다."
    ),
)
def list_low_balance_passes(
    academy_id: int,
    max_remaining: MaxRemaining = 3,
    available_only: bool = True,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "remaining_sessions",
        "expire_date",
        "student_name",
        "id",
    ] = "remaining_sessions",
    order: Order = "asc",
) -> dict:
    return db_connector.list_low_balance_passes(
        academy_id,
        max_remaining=max_remaining,
        available_only=available_only,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get(
    "/reregistration-candidates",
    response_model=ReregistrationCandidatesResponse,
    operation_id="list_reregistration_candidates",
    summary="재등록 후보 조회",
    description=(
        "재등록 안내가 필요한 수강생을 사유 코드와 함께 조회한다. "
        "한 수강생은 한 번만 반환하며 reasons에 모든 사유를 담는다. "
        "LOW_REMAINING_SESSIONS: 사용 가능한 수강권 잔여 합계가 "
        "max_remaining 이하. EXPIRING_SOON: 사용 가능한 수강권이 "
        "expiring_within_days 이내 만료. ALL_PASSES_EXHAUSTED: 보유 "
        "수강권 잔여 합계가 0. EXPIRED_WITH_RECENT_ATTENDANCE: 사용 "
        "가능한 수강권이 없고 만료된 수강권이 있으며 "
        "recent_attendance_days 이내 완료 수강 기록이 있음. "
        "remaining_sessions는 사용 가능한 수강권의 잔여 "
        "합계이며, 상담·연락 이력은 현재 스키마에 저장하지 않는다."
    ),
)
def list_reregistration_candidates(
    academy_id: int,
    max_remaining: MaxRemaining = 3,
    expiring_within_days: ExpiringDays = 14,
    recent_attendance_days: RecentDays = 30,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "nearest_expire_date",
        "remaining_sessions",
        "last_completed_at",
        "student_name",
        "student_id",
    ] = "nearest_expire_date",
    order: Order = "asc",
) -> dict:
    return db_connector.list_reregistration_candidates(
        academy_id,
        max_remaining=max_remaining,
        expiring_within_days=expiring_within_days,
        recent_attendance_days=recent_attendance_days,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )
