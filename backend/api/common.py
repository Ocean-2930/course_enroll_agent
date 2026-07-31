"""API 라우터가 공유하는 쿼리 파라미터 타입."""

from typing import Annotated, Literal

from fastapi import Query


Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Order = Literal["asc", "desc"]
AttendanceStatusQuery = Literal[
    "RESERVED",
    "CHECKED_IN",
    "COMPLETED",
    "CANCELLED",
]
InquiryStatusQuery = Literal["OPEN", "ANSWERED", "CLOSED"]
InquiryCategoryQuery = Literal[
    "PASS",
    "RESERVATION",
    "ATTENDANCE",
    "CHECK_IN_OUT",
    "DEDUCTION_ERROR",
    "EXTENSION",
    "REFUND",
    "FACILITY",
    "OTHER",
]
