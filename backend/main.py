"""수강권 장부 FastAPI 백엔드 진입점."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.router import api_router
from database.db_connector import DatabaseError

app = FastAPI(
    title="Course Enroll Agent API",
    description="SQLite 기반 수강권 장부 REST API",
    version="1.0.0",
)


@app.exception_handler(DatabaseError)
async def database_error_handler(
    request: Request,
    error: DatabaseError,
) -> JSONResponse:
    """예측 가능한 저장소 업무 오류를 공통 JSON으로 변환한다."""
    del request
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            }
        },
    )


@app.get("/ping", tags=["system"])
async def ping() -> dict[str, str]:
    """서버가 요청을 처리할 수 있는지 확인한다."""
    return {"status": "ok"}


app.include_router(api_router)
