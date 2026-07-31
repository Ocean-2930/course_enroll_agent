"""수강생 REST API."""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Response, status

from api.common import (
    AttendanceStatusQuery,
    Limit,
    Offset,
    Order,
)
from api.models import (
    AttendanceRecordResponse,
    Page,
    StudentCreate,
    StudentPassResponse,
    StudentResponse,
    StudentSummaryResponse,
    StudentUpdate,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/students",
    tags=["students"],
)


@router.get(
    "",
    response_model=Page[StudentResponse],
    operation_id="list_students",
    summary="수강생 목록 조회",
)
def list_students(
    academy_id: int,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    active: bool | None = None,
    expire_from: date | None = None,
    expire_to: date | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "id",
        "name",
        "expire_date",
        "created_at",
        "updated_at",
    ] = "id",
    order: Order = "asc",
) -> dict:
    return db_connector.list_students(
        academy_id,
        name=name,
        phone=phone,
        email=email,
        active=active,
        expire_from=expire_from.isoformat() if expire_from else None,
        expire_to=expire_to.isoformat() if expire_to else None,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.post(
    "",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_student",
    summary="수강생 생성",
)
def create_student(
    academy_id: int,
    payload: StudentCreate,
) -> dict:
    return db_connector.create_student(
        academy_id,
        payload.model_dump(),
    )


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
    operation_id="get_student",
    summary="수강생 상세 조회",
)
def get_student(academy_id: int, student_id: int) -> dict:
    return db_connector.get_student(academy_id, student_id)


@router.patch(
    "/{student_id}",
    response_model=StudentResponse,
    operation_id="update_student",
    summary="수강생 수정",
)
def update_student(
    academy_id: int,
    student_id: int,
    payload: StudentUpdate,
) -> dict:
    return db_connector.update_student(
        academy_id,
        student_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_student",
    summary="수강생 삭제",
)
def delete_student(academy_id: int, student_id: int) -> Response:
    db_connector.delete_student(academy_id, student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{student_id}/summary",
    response_model=StudentSummaryResponse,
    operation_id="get_student_summary",
    summary="수강생 요약 조회",
)
def get_student_summary(academy_id: int, student_id: int) -> dict:
    return db_connector.get_student_summary(academy_id, student_id)


@router.get(
    "/{student_id}/available-passes",
    response_model=list[StudentPassResponse],
    operation_id="list_student_available_passes",
    summary="사용 가능한 수강권 조회",
)
def list_available_passes(
    academy_id: int,
    student_id: int,
) -> list[dict]:
    return db_connector.list_available_student_passes(
        academy_id,
        student_id,
    )


@router.get(
    "/{student_id}/attendance-records",
    response_model=Page[AttendanceRecordResponse],
    operation_id="list_student_attendance_records",
    summary="수강생 전체 수강 기록 조회",
)
def list_student_attendance_records(
    academy_id: int,
    student_id: int,
    status: AttendanceStatusQuery | None = None,
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
    return db_connector.list_student_attendance_records(
        academy_id,
        student_id,
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
        sort=sort,
        order=order,
    )
