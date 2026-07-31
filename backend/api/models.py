"""REST API 요청과 응답 Pydantic 모델."""

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


AttendanceStatus = Literal["RESERVED", "COMPLETED", "CANCELLED"]
T = TypeVar("T")


class ApiModel(BaseModel):
    """알 수 없는 클라이언트 필드를 거부하는 API 기본 모델."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Pagination(ApiModel):
    limit: int
    offset: int
    total: int


class Page(ApiModel, Generic[T]):
    items: list[T]
    pagination: Pagination


class AcademyCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)


class AcademyUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def reject_null_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name은 null일 수 없습니다.")
        return value


class AcademyResponse(ApiModel):
    id: int
    name: str
    phone: str | None
    address: str | None
    created_at: datetime
    updated_at: datetime


class StudentCounts(ApiModel):
    total: int
    active: int
    inactive: int


class PassCounts(ApiModel):
    pass_type_count: int
    student_pass_count: int
    available_pass_count: int
    total_remaining_sessions: int


class TodayAttendanceCounts(ApiModel):
    reserved: int
    completed: int
    cancelled: int


class AcademySummaryResponse(ApiModel):
    academy_id: int
    students: StudentCounts
    passes: PassCounts
    today_attendance: TodayAttendanceCounts


class PassTypeCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    total_sessions: int = Field(gt=0)
    validity_days: int = Field(gt=0)
    price: int = Field(default=0, ge=0)


class PassTypeUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    total_sessions: int | None = Field(default=None, gt=0)
    validity_days: int | None = Field(default=None, gt=0)
    price: int | None = Field(default=None, ge=0)
    sort_index: int | None = Field(default=None, ge=0)

    @field_validator(
        "name",
        "total_sessions",
        "validity_days",
        "price",
        "sort_index",
    )
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("필수 상품 필드는 null일 수 없습니다.")
        return value


class PassTypeResponse(ApiModel):
    id: int
    academy_id: int
    name: str
    description: str | None
    total_sessions: int
    validity_days: int
    price: int
    sort_index: int
    created_at: datetime
    updated_at: datetime


class StudentCreate(ApiModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=320)
    memo: str | None = None


class StudentUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=320)
    memo: str | None = None

    @field_validator("name")
    @classmethod
    def reject_null_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name은 null일 수 없습니다.")
        return value


class StudentResponse(ApiModel):
    id: int
    academy_id: int
    name: str
    phone: str | None
    email: str | None
    memo: str | None
    expire_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentSummaryIdentity(ApiModel):
    id: int
    name: str
    expire_date: date | None
    is_active: bool


class StudentPassCounts(ApiModel):
    total_count: int
    available_count: int
    total_remaining_sessions: int


class StudentAttendanceCounts(ApiModel):
    reserved_count: int
    completed_count: int
    cancelled_count: int
    last_completed_at: datetime | None


class StudentSummaryResponse(ApiModel):
    student: StudentSummaryIdentity
    passes: StudentPassCounts
    attendance: StudentAttendanceCounts


class StudentPassCreate(ApiModel):
    pass_type_id: int = Field(gt=0)
    purchased_at: datetime | None = None
    started_at: datetime | None = None


class StudentPassUpdate(ApiModel):
    started_at: datetime | None = None
    expire_date: date | None = None

    @field_validator("expire_date")
    @classmethod
    def reject_null_expire_date(cls, value: date | None) -> date:
        if value is None:
            raise ValueError("expire_date는 null일 수 없습니다.")
        return value


class StudentPassResponse(ApiModel):
    id: int
    student_id: int
    pass_type_id: int | None
    pass_type_id_snapshot: int
    pass_type_name_snapshot: str
    total_sessions: int
    remaining_sessions: int
    validity_days_snapshot: int
    price_snapshot: int
    purchased_at: datetime
    started_at: datetime | None
    expire_date: date
    used_sessions: int
    is_expired: bool
    is_available: bool
    pass_type_exists: bool
    created_at: datetime
    updated_at: datetime


class StudentPassIssueResponse(StudentPassResponse):
    student_expire_date: date


class AttendanceRecordCreate(ApiModel):
    student_id: int = Field(gt=0)
    student_pass_id: int = Field(gt=0)
    class_name: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime
    memo: str | None = None


class AttendanceRecordUpdate(ApiModel):
    class_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    scheduled_at: datetime | None = None
    memo: str | None = None

    @field_validator("class_name", "scheduled_at")
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("필수 예약 필드는 null일 수 없습니다.")
        return value


class AttendanceCompleteRequest(ApiModel):
    completed_at: datetime | None = None


class AttendanceCancelRequest(ApiModel):
    cancelled_at: datetime | None = None
    memo: str | None = None


class AttendanceRestoreRequest(ApiModel):
    reason: str = Field(min_length=1)
    cancelled_at: datetime | None = None


class AttendanceRecordResponse(ApiModel):
    id: int
    academy_id: int | None
    student_id: int | None
    student_pass_id: int | None
    student_name: str
    student_name_snapshot: str
    pass_type_id: int
    pass_type_name: str
    pass_type_id_snapshot: int
    pass_type_name_snapshot: str
    class_name: str
    scheduled_at: datetime
    status: AttendanceStatus
    session_delta: int
    cancelled_at: datetime | None
    completed_at: datetime | None
    memo: str | None
    created_at: datetime
    updated_at: datetime


class HealthResponse(ApiModel):
    status: Literal["ok"]
    database: Literal["connected"]
