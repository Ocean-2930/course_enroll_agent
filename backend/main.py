"""수강권 장부 FastAPI 백엔드 진입점."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.router import api_router
from database.db_connector import DatabaseError

app = FastAPI(
    title="Course Enroll Agent API",
    description="SQLite 기반 수강권 장부 REST API",
    version="1.0.0",
)

# 로컬 개발용 CORS.
# - localhost / 127.0.0.1 의 모든 포트(Live Server, Vite 등)를 허용한다.
# - file:// 로 직접 연 정적 페이지는 Origin 이 "null" 로 전송되므로 함께 허용한다.
# 인증 쿠키를 사용하지 않으므로 allow_credentials 는 켜지 않는다(운영 배포 시 재검토).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
