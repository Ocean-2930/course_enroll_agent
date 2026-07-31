"""`/api` 메인 라우터를 구성한다."""

from fastapi import APIRouter

from api import (
    academies,
    analytics,
    attendance_records,
    checks,
    inquiries,
    pass_types,
    student_passes,
    students,
    worklists,
)
from api.models import HealthResponse
from database import db_connector


api_router = APIRouter(prefix="/api")


@api_router.get(
    "/health",
    response_model=HealthResponse,
    operation_id="check_health",
    tags=["system"],
    summary="서버 및 데이터베이스 상태 확인",
)
def health() -> dict[str, str]:
    return db_connector.health_check()


api_router.include_router(academies.router)
api_router.include_router(pass_types.router)
api_router.include_router(students.router)
api_router.include_router(student_passes.router)
api_router.include_router(attendance_records.router)
api_router.include_router(inquiries.router)
api_router.include_router(analytics.router)
api_router.include_router(worklists.router)
api_router.include_router(checks.router)
