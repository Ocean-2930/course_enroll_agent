"""운영 분석(집계) 조회 REST API.

조회 전용이며 어떤 데이터도 변경하지 않는다. 기간은 자연어가 아니라
`date_from`, `date_to` 같은 구조화된 값으로만 받는다.
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Query

from api.common import Limit, Offset, Order
from api.models import (
    AttendanceAnalyticsResponse,
    DashboardAnalyticsResponse,
    GroupBy,
    PassTypeAnalyticsResponse,
    RegistrationAnalyticsResponse,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/analytics",
    tags=["analytics"],
)

DateFrom = Query(
    default=None,
    description="조회 시작일(YYYY-MM-DD). 생략하면 종료일 기준 최근 30일.",
)
DateTo = Query(
    default=None,
    description="조회 종료일(YYYY-MM-DD). 생략하면 오늘.",
)


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


@router.get(
    "/dashboard",
    response_model=DashboardAnalyticsResponse,
    operation_id="get_academy_dashboard",
    summary="운영 대시보드 요약 조회",
    description=(
        "아카데미 운영 KPI를 한 번에 조회한다. "
        "students.new_in_period는 기간 내 등록된 수강생 수, "
        "student_passes.issued_in_period는 구매일 기준 기간 내 발급 건수, "
        "attendance의 기간 집계는 수업 예정일 기준이다. "
        "attendance.pending_past는 기간과 무관하게 현재 시각보다 예정 "
        "시각이 과거인 RESERVED 예약 수이며 결석 확정이 아니다. "
        "expiring_within_14_days는 오늘부터 14일 이내 만료되는 잔여 "
        "1회 이상 수강권, low_balance_count는 만료 전 수강권 중 잔여 "
        "3회 이하(0회 포함)를 뜻한다."
    ),
)
def get_academy_dashboard(
    academy_id: int,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
) -> dict:
    return db_connector.get_dashboard_analytics(
        academy_id,
        date_from=_iso(date_from),
        date_to=_iso(date_to),
    )


@router.get(
    "/registrations",
    response_model=RegistrationAnalyticsResponse,
    operation_id="get_registration_analytics",
    summary="신규 등록 통계 조회",
    description=(
        "신규 수강생 수와 수강권 발급 건수를 기간·단위별로 집계한다. "
        "수강생은 등록일(created_at), 수강권은 구매일(purchased_at)을 "
        "기준으로 한다. previous_period는 선택 기간과 같은 길이의 직전 "
        "기간이며, 직전 기간 값이 0이면 변화율(rate)은 null이다. "
        "series는 데이터가 없는 구간도 0으로 채워 반환한다."
    ),
)
def get_registration_analytics(
    academy_id: int,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    group_by: GroupBy = "day",
) -> dict:
    return db_connector.get_registration_analytics(
        academy_id,
        date_from=_iso(date_from),
        date_to=_iso(date_to),
        group_by=group_by,
    )


@router.get(
    "/attendance",
    response_model=AttendanceAnalyticsResponse,
    operation_id="get_attendance_analytics",
    summary="수강 이용 통계 조회",
    description=(
        "수업 예정일(scheduled_at)을 기준으로 예약·완료·취소 건수를 "
        "집계한다. totals.pending_past는 선택 기간 안에서 예정 시각이 "
        "이미 지난 RESERVED 예약 수이며 결석 확정이 아니다. "
        "by_class_name은 자유 입력 수업명을 그대로 묶으므로 표기가 "
        "다르면 다른 항목으로 집계된다."
    ),
)
def get_attendance_analytics(
    academy_id: int,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    group_by: GroupBy = "day",
) -> dict:
    return db_connector.get_attendance_analytics(
        academy_id,
        date_from=_iso(date_from),
        date_to=_iso(date_to),
        group_by=group_by,
    )


@router.get(
    "/pass-types",
    response_model=PassTypeAnalyticsResponse,
    operation_id="get_pass_type_analytics",
    summary="수강권 종류별 이용 통계 조회",
    description=(
        "기간 내 발급된 보유 수강권을 발급 시점 종류 스냅샷 기준으로 "
        "묶어 집계한다. 원본 수강권 종류가 삭제돼도 스냅샷 이름으로 "
        "집계된다. issued_price_total은 실제 매출이 아니라 발급 시점 "
        "가격(price_snapshot)의 합계다. completed_attendance_count는 "
        "해당 수강권들에 연결된 완료 기록 수로 기간 제한이 없다."
    ),
)
def get_pass_type_analytics(
    academy_id: int,
    date_from: date | None = DateFrom,
    date_to: date | None = DateTo,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "issued_count",
        "issued_sessions",
        "issued_price_total",
        "remaining_sessions",
        "used_sessions",
        "completed_attendance_count",
        "pass_type_name",
        "pass_type_id",
    ] = "issued_count",
    order: Order = "desc",
) -> dict:
    return db_connector.get_pass_type_analytics(
        academy_id,
        date_from=_iso(date_from),
        date_to=_iso(date_to),
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )
