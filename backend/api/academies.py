"""아카데미 REST API."""

from typing import Literal

from fastapi import APIRouter, Query, Response, status

from api.common import Limit, Offset, Order
from api.models import (
    AcademyCreate,
    AcademyResponse,
    AcademySummaryResponse,
    AcademyUpdate,
    Page,
)
from database import db_connector


router = APIRouter(prefix="/academies", tags=["academies"])


@router.get(
    "",
    response_model=Page[AcademyResponse],
    summary="아카데미 목록 조회",
)
def list_academies(
    name: str | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal["id", "name", "created_at", "updated_at"] = "id",
    order: Order = "asc",
) -> dict:
    return db_connector.list_academies(
        name=name,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.post(
    "",
    response_model=AcademyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="아카데미 생성",
)
def create_academy(payload: AcademyCreate) -> dict:
    return db_connector.create_academy(payload.model_dump())


@router.get(
    "/{academy_id}",
    response_model=AcademyResponse,
    summary="아카데미 상세 조회",
)
def get_academy(academy_id: int) -> dict:
    return db_connector.get_academy(academy_id)


@router.patch(
    "/{academy_id}",
    response_model=AcademyResponse,
    summary="아카데미 수정",
)
def update_academy(
    academy_id: int,
    payload: AcademyUpdate,
) -> dict:
    return db_connector.update_academy(
        academy_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{academy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="아카데미 삭제",
)
def delete_academy(academy_id: int) -> Response:
    db_connector.delete_academy(academy_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{academy_id}/summary",
    response_model=AcademySummaryResponse,
    summary="아카데미 요약 조회",
)
def get_academy_summary(academy_id: int) -> dict:
    return db_connector.get_academy_summary(academy_id)
