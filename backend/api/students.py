"""수강생 REST API."""

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Response, status

from api.common import (
    AttendanceStatusQuery,
    InquiryCategoryQuery,
    InquiryStatusQuery,
    Limit,
    Offset,
    Order,
)
from api.models import (
    AttendanceRecordResponse,
    InquiryCreate,
    InquiryDetailResponse,
    InquiryMessageCreate,
    InquirySummaryResponse,
    Page,
    StudentCreate,
    StudentPassResponse,
    StudentPortalSummaryResponse,
    StudentReservationItem,
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


# =========================================================
# 회원 포털 전용 조회
# 현재 인증이 없으므로 경로의 student_id 는 보안 경계가 아니라
# 화면에서 고른 값일 뿐이다. 운영 전 인증·권한 검증이 필요하다.
# =========================================================


@router.get(
    "/{student_id}/portal-summary",
    response_model=StudentPortalSummaryResponse,
    operation_id="get_student_portal_summary",
    summary="회원 홈 요약 조회",
    description=(
        "회원 포털 홈에 필요한 값을 한 번에 조회한다. 보유 수강권 요약, "
        "오늘 일정 수, 다음 예약, 현재 체크인 중인 수강, 최근 이용 내역, "
        "문의 상태별 건수를 담는다. 조회 전용이다."
    ),
)
def get_student_portal_summary(academy_id: int, student_id: int) -> dict:
    return db_connector.get_student_portal_summary(academy_id, student_id)


@router.get(
    "/{student_id}/reservations",
    response_model=Page[StudentReservationItem],
    operation_id="list_student_reservations",
    summary="회원 예약 목록 조회",
    description=(
        "회원의 예약을 수강권 잔여 횟수와 함께 조회한다. "
        "upcoming_only=true 이면 아직 처리되지 않은 기록만 반환한다. "
        "RESERVED 는 종료 예정 시각이 현재 이후인 것만, CHECKED_IN 은 "
        "퇴실이 남아 있으므로 시각과 무관하게 모두 포함한다."
    ),
)
def list_student_reservations(
    academy_id: int,
    student_id: int,
    status: AttendanceStatusQuery | None = None,
    scheduled_from: datetime | None = None,
    scheduled_to: datetime | None = None,
    upcoming_only: bool = False,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "scheduled_at",
        "id",
        "status",
        "class_name",
        "created_at",
    ] = "scheduled_at",
    order: Order = "desc",
) -> dict:
    return db_connector.list_student_reservations(
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
        upcoming_only=upcoming_only,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


# ---------- 회원 문의 ----------


@router.get(
    "/{student_id}/inquiries",
    response_model=Page[InquirySummaryResponse],
    operation_id="list_student_inquiries",
    summary="회원 문의 목록 조회",
)
def list_student_inquiries(
    academy_id: int,
    student_id: int,
    status: InquiryStatusQuery | None = None,
    category: InquiryCategoryQuery | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "created_at",
        "updated_at",
        "id",
        "status",
        "category",
    ] = "created_at",
    order: Order = "desc",
) -> dict:
    return db_connector.list_student_inquiries(
        academy_id,
        student_id,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.post(
    "/{student_id}/inquiries",
    response_model=InquiryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_student_inquiry",
    summary="회원 문의 등록",
    description=(
        "문의와 최초 메시지(sender_type=STUDENT)를 한 트랜잭션으로 "
        "생성한다. 초기 상태는 OPEN 이다. 관련 수강권·수강 기록을 "
        "지정하면 본인 것인지 검증한다."
    ),
)
def create_student_inquiry(
    academy_id: int,
    student_id: int,
    payload: InquiryCreate,
) -> dict:
    return db_connector.create_inquiry(
        academy_id,
        student_id,
        payload.model_dump(),
    )


@router.get(
    "/{student_id}/inquiries/{inquiry_id}",
    response_model=InquiryDetailResponse,
    operation_id="get_student_inquiry",
    summary="회원 문의 상세 조회",
)
def get_student_inquiry(
    academy_id: int,
    student_id: int,
    inquiry_id: int,
) -> dict:
    return db_connector.get_student_inquiry(
        academy_id,
        student_id,
        inquiry_id,
    )


@router.post(
    "/{student_id}/inquiries/{inquiry_id}/messages",
    response_model=InquiryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_student_inquiry_message",
    summary="회원 문의 메시지 추가",
    description=(
        "sender_type 은 서버가 STUDENT 로 설정한다. 회원이 메시지를 "
        "추가하면 상태는 다시 OPEN(답변 대기)이 된다. 종료된 문의에는 "
        "추가할 수 없다."
    ),
)
def add_student_inquiry_message(
    academy_id: int,
    student_id: int,
    inquiry_id: int,
    payload: InquiryMessageCreate,
) -> dict:
    return db_connector.add_student_inquiry_message(
        academy_id,
        student_id,
        inquiry_id,
        payload.message,
    )


@router.post(
    "/{student_id}/inquiries/{inquiry_id}/close",
    response_model=InquiryDetailResponse,
    operation_id="close_student_inquiry",
    summary="회원 문의 종료",
)
def close_student_inquiry(
    academy_id: int,
    student_id: int,
    inquiry_id: int,
) -> dict:
    return db_connector.close_student_inquiry(
        academy_id,
        student_id,
        inquiry_id,
    )
