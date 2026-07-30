"""수강생 보유 수강권 REST API."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Response, status

from api.common import AttendanceStatusQuery, Limit, Offset, Order
from api.models import (
    AttendanceRecordResponse,
    Page,
    StudentPassCreate,
    StudentPassIssueResponse,
    StudentPassResponse,
    StudentPassUpdate,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/students/{student_id}/passes",
    tags=["student-passes"],
)


@router.get(
    "",
    response_model=Page[StudentPassResponse],
    summary="보유 수강권 목록 조회",
)
def list_student_passes(
    academy_id: int,
    student_id: int,
    available: bool | None = None,
    expired: bool | None = None,
    pass_type_id: int | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "id",
        "purchased_at",
        "started_at",
        "expire_date",
        "remaining_sessions",
        "created_at",
    ] = "id",
    order: Order = "asc",
) -> dict:
    return db_connector.list_student_passes(
        academy_id,
        student_id,
        available=available,
        expired=expired,
        pass_type_id=pass_type_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.post(
    "",
    response_model=StudentPassIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="수강권 발급",
    description="수강권 발급과 학생 만료일 갱신을 한 트랜잭션으로 처리합니다.",
)
def issue_student_pass(
    academy_id: int,
    student_id: int,
    payload: StudentPassCreate,
) -> dict:
    return db_connector.issue_student_pass(
        academy_id,
        student_id,
        payload.model_dump(),
    )


@router.get(
    "/{student_pass_id}",
    response_model=StudentPassResponse,
    summary="보유 수강권 상세 조회",
)
def get_student_pass(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
) -> dict:
    return db_connector.get_student_pass(
        academy_id,
        student_id,
        student_pass_id,
    )


@router.patch(
    "/{student_pass_id}",
    response_model=StudentPassResponse,
    summary="보유 수강권 수정",
)
def update_student_pass(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
    payload: StudentPassUpdate,
) -> dict:
    return db_connector.update_student_pass(
        academy_id,
        student_id,
        student_pass_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{student_pass_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="보유 수강권 삭제",
)
def delete_student_pass(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
) -> Response:
    db_connector.delete_student_pass(
        academy_id,
        student_id,
        student_pass_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{student_pass_id}/attendance-records",
    response_model=Page[AttendanceRecordResponse],
    summary="보유 수강권별 수강 기록 조회",
)
def list_student_pass_attendance_records(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
    status: AttendanceStatusQuery | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
) -> dict:
    return db_connector.list_student_pass_attendance_records(
        academy_id,
        student_id,
        student_pass_id,
        status=status,
        scheduled_from=(
            scheduled_from.replace(microsecond=0).isoformat()
            if scheduled_from
            else None
        ),
        scheduled_to=(
            scheduled_to.replace(microsecond=0).isoformat()
            if scheduled_to
            else None
        ),
        limit=limit,
        offset=offset,
    )
