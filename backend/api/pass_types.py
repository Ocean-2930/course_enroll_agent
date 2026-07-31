"""수강권 종류 REST API."""

from typing import Literal

from fastapi import APIRouter, Query, Response, status

from api.common import Limit, Offset, Order
from api.models import (
    Page,
    PassTypeCreate,
    PassTypeResponse,
    PassTypeUpdate,
)
from database import db_connector


router = APIRouter(
    prefix="/academies/{academy_id}/pass-types",
    tags=["pass-types"],
)


@router.get(
    "",
    response_model=Page[PassTypeResponse],
    operation_id="list_pass_types",
    summary="수강권 종류 목록 조회",
)
def list_pass_types(
    academy_id: int,
    name: str | None = None,
    min_price: int | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0),
    limit: Limit = 20,
    offset: Offset = 0,
    sort: Literal[
        "id",
        "name",
        "price",
        "total_sessions",
        "validity_days",
        "sort_index",
        "created_at",
    ] = "sort_index",
    order: Order = "asc",
) -> dict:
    return db_connector.list_pass_types(
        academy_id,
        name=name,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.post(
    "",
    response_model=PassTypeResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="create_pass_type",
    summary="수강권 종류 생성",
)
def create_pass_type(
    academy_id: int,
    payload: PassTypeCreate,
) -> dict:
    return db_connector.create_pass_type(
        academy_id,
        payload.model_dump(),
    )


@router.get(
    "/{pass_type_id}",
    response_model=PassTypeResponse,
    operation_id="get_pass_type",
    summary="수강권 종류 상세 조회",
)
def get_pass_type(academy_id: int, pass_type_id: int) -> dict:
    return db_connector.get_pass_type(academy_id, pass_type_id)


@router.patch(
    "/{pass_type_id}",
    response_model=PassTypeResponse,
    operation_id="update_pass_type",
    summary="수강권 종류 수정",
)
def update_pass_type(
    academy_id: int,
    pass_type_id: int,
    payload: PassTypeUpdate,
) -> dict:
    return db_connector.update_pass_type(
        academy_id,
        pass_type_id,
        payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/{pass_type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_pass_type",
    summary="수강권 종류 삭제",
)
def delete_pass_type(
    academy_id: int,
    pass_type_id: int,
) -> Response:
    db_connector.delete_pass_type(academy_id, pass_type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
