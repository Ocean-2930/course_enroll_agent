"""예약 및 수강 기록 REST API."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter

from api.common import (
    AttendanceStatusQuery,
    Limit,
    Offset,
    Order,
)
from api.models import (
    AttendanceActionResponse,
    AttendanceCancelRequest,
    AttendanceCompleteRequest,
    AttendanceRecordCreate,
    AttendanceRecordResponse,
    AttendanceRecordUpdate,
    AttendanceRestoreRequest,
    Page,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/attendance-records",
    tags=["attendance-records"],
)


def _iso(value: datetime | None) -> str | None:
    return (
        value.replace(microsecond=0).isoformat()
        if value is not None
        else None
    )


@router.get(
    "",
    response_model=Page[AttendanceRecordResponse],
    operation_id="list_attendance_records",
    summary="수강 기록 목록 조회",
)
def list_attendance_records(
    academy_id: int,
    student_id: int | None = None,
    student_pass_id: int | None = None,
    pass_type_id_snapshot: int | None = None,
    status: AttendanceStatusQuery | None = None,
    class_name: str | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "id",
        "scheduled_at",
        "created_at",
        "updated_at",
        "status",
        "class_name",
    ] = "scheduled_at",
    order: Order = "desc",
) -> dict:
    return db_connector.list_attendance_records(
        academy_id,
        student_id=student_id,
        student_pass_id=student_pass_id,
        pass_type_id_snapshot=pass_type_id_snapshot,
        status=status,
        class_name=class_name,
        scheduled_from=_iso(scheduled_from),
        scheduled_to=_iso(scheduled_to),
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.post(
    "",
    response_model=AttendanceRecordResponse,
    status_code=201,
    operation_id="create_attendance_reservation",
    summary="예약 생성",
    description="예약 생성 시 횟수는 차감하지 않습니다.",
)
def create_attendance_record(
    academy_id: int,
    payload: AttendanceRecordCreate,
) -> dict:
    return db_connector.create_attendance_record(
        academy_id,
        payload.model_dump(),
    )


@router.get(
    "/{attendance_record_id}",
    response_model=AttendanceRecordResponse,
    operation_id="get_attendance_record",
    summary="수강 기록 상세 조회",
)
def get_attendance_record(
    academy_id: int,
    attendance_record_id: int,
) -> dict:
    return db_connector.get_attendance_record(
        academy_id,
        attendance_record_id,
    )


@router.patch(
    "/{attendance_record_id}",
    response_model=AttendanceRecordResponse,
    operation_id="update_attendance_record",
    summary="예약 내용 수정",
)
def update_attendance_record(
    academy_id: int,
    attendance_record_id: int,
    payload: AttendanceRecordUpdate,
) -> dict:
    return db_connector.update_attendance_record(
        academy_id,
        attendance_record_id,
        payload.model_dump(exclude_unset=True),
    )


@router.post(
    "/{attendance_record_id}/check-in",
    response_model=AttendanceActionResponse,
    operation_id="check_in_attendance",
    summary="출석 체크인",
    description=(
        "RESERVED 예약을 CHECKED_IN 으로 바꾸고 체크인 시각을 기록한다. "
        "이 시점에는 잔여 횟수를 차감하지 않는다. 이미 체크인했으면 "
        "409 ATTENDANCE_ALREADY_CHECKED_IN, 예약 상태가 아니면 "
        "409 ATTENDANCE_NOT_RESERVED 를 반환한다. 현재는 체크인 가능 "
        "시간 범위를 제한하지 않는다."
    ),
)
def check_in_attendance(
    academy_id: int,
    attendance_record_id: int,
) -> dict:
    return db_connector.check_in_attendance(
        academy_id,
        attendance_record_id,
    )


@router.post(
    "/{attendance_record_id}/check-out",
    response_model=AttendanceActionResponse,
    operation_id="check_out_attendance",
    summary="퇴실 및 수강 완료",
    description=(
        "CHECKED_IN 수강을 COMPLETED 로 바꾸고 퇴실·완료 시각을 기록하며 "
        "잔여 횟수를 1회 차감한다. 상태 변경과 차감은 한 트랜잭션이라 "
        "중복 요청이 두 번 차감되지 않는다."
    ),
)
def check_out_attendance(
    academy_id: int,
    attendance_record_id: int,
) -> dict:
    return db_connector.check_out_attendance(
        academy_id,
        attendance_record_id,
    )


@router.post(
    "/{attendance_record_id}/complete",
    response_model=AttendanceRecordResponse,
    operation_id="complete_attendance",
    summary="수강 완료 처리(사업자)",
    description=(
        "RESERVED 와 CHECKED_IN 모두 완료 처리할 수 있습니다. 잔여 횟수 "
        "차감과 완료 처리를 한 트랜잭션으로 수행합니다. 예약 상태에서 "
        "바로 완료하면 완료 시각을 체크인 시각으로도 기록합니다."
    ),
)
def complete_attendance(
    academy_id: int,
    attendance_record_id: int,
    payload: AttendanceCompleteRequest,
) -> dict:
    return db_connector.complete_attendance(
        academy_id,
        attendance_record_id,
        _iso(payload.completed_at),
    )


@router.post(
    "/{attendance_record_id}/cancel",
    response_model=AttendanceRecordResponse,
    operation_id="cancel_attendance",
    summary="예약 취소",
)
def cancel_attendance(
    academy_id: int,
    attendance_record_id: int,
    payload: AttendanceCancelRequest,
) -> dict:
    return db_connector.cancel_attendance(
        academy_id,
        attendance_record_id,
        cancelled_at=_iso(payload.cancelled_at),
        memo=payload.memo,
    )


@router.post(
    "/{attendance_record_id}/restore",
    response_model=AttendanceRecordResponse,
    operation_id="restore_attendance",
    summary="완료된 수강 취소 및 횟수 복구",
    description=(
        "현재 스키마는 append-only 감사 이력이 아니며 기존 기록을 "
        "CANCELLED 상태로 변경합니다."
    ),
)
def restore_attendance(
    academy_id: int,
    attendance_record_id: int,
    payload: AttendanceRestoreRequest,
) -> dict:
    return db_connector.restore_attendance(
        academy_id,
        attendance_record_id,
        reason=payload.reason,
        cancelled_at=_iso(payload.cancelled_at),
    )
