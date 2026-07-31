"""아카데미(사업자) 문의 REST API.

회원용 문의 API는 `api/students.py` 의 수강생 경로 아래에 있다.
"""

from typing import Literal

from fastapi import APIRouter, status

from api.common import (
    InquiryCategoryQuery,
    InquiryStatusQuery,
    Limit,
    Offset,
    Order,
)
from api.models import (
    InquiryDetailResponse,
    InquiryMessageCreate,
    InquirySummaryResponse,
    Page,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/inquiries",
    tags=["inquiries"],
)


@router.get(
    "",
    response_model=Page[InquirySummaryResponse],
    operation_id="list_academy_inquiries",
    summary="아카데미 문의 목록 조회",
    description=(
        "아카데미로 접수된 문의를 조회한다. student_id 로 특정 회원의 "
        "문의만 좁힐 수 있다. 조회 전용이다."
    ),
)
def list_academy_inquiries(
    academy_id: int,
    student_id: int | None = None,
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
    return db_connector.list_academy_inquiries(
        academy_id,
        student_id=student_id,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get(
    "/{inquiry_id}",
    response_model=InquiryDetailResponse,
    operation_id="get_academy_inquiry",
    summary="아카데미 문의 상세 조회",
)
def get_academy_inquiry(academy_id: int, inquiry_id: int) -> dict:
    return db_connector.get_academy_inquiry(academy_id, inquiry_id)


@router.post(
    "/{inquiry_id}/messages",
    response_model=InquiryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="add_academy_inquiry_message",
    summary="아카데미 답변 등록",
    description=(
        "sender_type 은 서버가 ACADEMY 로 설정하고 문의 상태를 ANSWERED "
        "로 바꾼다. 종료된 문의에는 답변할 수 없다."
    ),
)
def add_academy_inquiry_message(
    academy_id: int,
    inquiry_id: int,
    payload: InquiryMessageCreate,
) -> dict:
    return db_connector.add_academy_inquiry_message(
        academy_id,
        inquiry_id,
        payload.message,
    )


@router.post(
    "/{inquiry_id}/close",
    response_model=InquiryDetailResponse,
    operation_id="close_academy_inquiry",
    summary="아카데미 문의 종료",
)
def close_academy_inquiry(academy_id: int, inquiry_id: int) -> dict:
    return db_connector.close_academy_inquiry(academy_id, inquiry_id)
