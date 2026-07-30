# Backend 개발 지침

## 적용 범위

이 파일은 `course_enroll_agent/backend/`와 그 하위 파일에 적용된다.

백엔드는 FastAPI와 SQLite를 사용한다. 현재 구성은 작지만 기능이 늘어날 것을 고려해 API, 데이터 모델, 데이터 접근 책임을 분리한다.

## 현재 파일의 역할

| 파일 | 역할 |
|---|---|
| `main.py` | FastAPI 앱 생성과 서버 진입점 |
| `api/` | `/api` 라우팅, Pydantic 요청·응답 모델, HTTP 처리 |
| `database/db_connector.py` | API가 사용하는 유일한 데이터 저장소 인터페이스 |
| `database/connection.py` | SQLite 연결 생성과 연결별 PRAGMA 설정 |
| `database/schema.py` | 초기화 시 적용할 전체 SQLite 스키마 |
| `init_db.py` | 기존 SQLite 파일 삭제 및 전체 DB 스키마 재생성 |
| `requirements.txt` | 백엔드에서 사용하는 외부 Python 라이브러리 |
| `init_venv.bat` | `.venv` 생성과 의존성 설치 |
| `runserver.bat` | 가상환경 활성화와 8000 포트 서버 실행 |
| `local_database.db` | 실행 중 생성되는 로컬 SQLite DB, Git 추적 제외 |

## FastAPI 앱

FastAPI 애플리케이션 객체는 `main.py`의 `app`이다.

```python
from fastapi import FastAPI

app = FastAPI(...)
```

상태 확인 엔드포인트:

```http
GET /api/health
```

성공 응답:

```json
{
  "status": "ok"
}
```

## 새로운 API 엔드포인트 추가 방법

### 1. 먼저 계약을 정의한다

구현 전에 다음을 결정한다.

- HTTP 메서드
- URL 경로
- 요청 본문 또는 쿼리 파라미터
- 성공 상태 코드
- 성공 응답 JSON
- 입력 오류 응답
- 대상 데이터와 권한

리소스 중심 URL을 사용한다.

```text
권장:
GET    /courses
GET    /courses/{course_id}
POST   /enrollments
DELETE /enrollments/{enrollment_id}

지양:
POST /getCourses
POST /doEnrollment
```

### 2. 요청·응답 모델을 만든다

외부 입력을 `dict`로 임의 처리하지 말고 Pydantic 모델로 검증한다.

```python
from pydantic import BaseModel, Field


class EnrollmentCreate(BaseModel):
    course_id: int = Field(gt=0)
    student_name: str = Field(min_length=1, max_length=100)


class EnrollmentResponse(BaseModel):
    id: int
    course_id: int
    student_name: str
```

응답 모델에는 내부 DB 컬럼이나 비밀정보를 그대로 노출하지 않는다.

### 3. 라우트를 구현한다

업무 라우트는 `api/`의 리소스별 모듈에 추가한다.

```python
from fastapi import status


@app.post(
    "/enrollments",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_enrollment(payload: EnrollmentCreate) -> EnrollmentResponse:
    ...
```

```text
backend/
├─ main.py
├─ api/
│  ├─ router.py
│  ├─ models.py
│  └─ 리소스별 라우터
└─ database/
   ├─ db_connector.py
   ├─ connection.py
   └─ schema.py
```

`main.py`는 앱 생성과 라우터 등록만 담당하게 한다.

```python
from api.router import api_router

app.include_router(api_router)
```

### 4. 상태 코드와 오류를 명확히 한다

- 조회 성공: `200 OK`
- 생성 성공: `201 Created`
- 삭제 성공, 본문 없음: `204 No Content`
- 잘못된 사용자 입력: `400 Bad Request`
- 인증 필요: `401 Unauthorized`
- 권한 없음: `403 Forbidden`
- 리소스 없음: `404 Not Found`
- 중복 또는 상태 충돌: `409 Conflict`

예측 가능한 업무 오류는 `HTTPException`으로 명확히 반환한다.

```python
from fastapi import HTTPException


raise HTTPException(
    status_code=404,
    detail="강좌를 찾을 수 없습니다.",
)
```

서버 내부 예외 내용, SQL, 파일 경로, 스택 트레이스를 응답에 노출하지 않는다.

### 5. DB 교체가 가능한 경계를 지킨다

라우트 함수 안에서는 SQL과 SQLite 연결을 전혀 다루지 않는다.

```text
api/
  → 요청 검증, HTTP 상태 코드, 응답 모델
database/db_connector.py
  → 데이터 접근, 소속 검증, 업무 오류, 트랜잭션
```

- API 모듈은 `database.db_connector`만 호출한다.
- API 모듈에서 `sqlite3`, `database.connection`, SQL 문자열을 사용하지
  않는다.
- 모든 CRUD와 조회용 SQL은 `database/db_connector.py`에 둔다.
- 복합 작업의 트랜잭션도 `db_connector.py`의 한 공개 함수 안에서
  완료한다.
- `db_connector.py`의 공개 함수 인자, 반환 딕셔너리와 `DatabaseError`
  계약을 안정적으로 유지한다.
- 다른 데이터베이스로 변경할 때 API 코드를 수정하지 않고 동일한 공개
  인터페이스를 구현한 `db_connector.py`로 교체할 수 있어야 한다.
- `database/schema.py`의 DDL과 초기화 테스트는 런타임 API 접근 경계의
  예외다.

## SQLite 데이터베이스

DB 파일은 항상 `init_db.py`와 같은 디렉터리에 생성한다.

```python
DATABASE_PATH = Path(__file__).resolve().parent / "local_database.db"
```

현재 작업 디렉터리에 의존하는 상대 경로는 사용하지 않는다.

### 스키마 작성 위치

새 테이블, 인덱스, 제약조건 등 DB 스키마를 만들거나 변경하려면 반드시
`database/schema.py`의 전체 생성문에 반영한다.

다음과 같은 테이블 생성문을 API 라우트나 서버 시작 코드에 흩어놓지 않는다.

```sql
CREATE TABLE IF NOT EXISTS courses (...);
CREATE INDEX IF NOT EXISTS idx_courses_name ON courses(name);
```

`main.py`의 API 호출 중 임의로 테이블을 생성하지 않는다. DB 준비는 다음
명령으로 명시적으로 수행한다. 이 명령은 기존 DB 파일과 저장된 데이터를
모두 삭제한 후 새 DB를 생성한다.

```text
python init_db.py
```

### 스키마 변경 원칙

- `init_db.py`는 기존 DB를 삭제하고 현재 전체 스키마를 새로 설정한다.
- 기존 데이터를 보존하는 마이그레이션은 관리하지 않는다.
- 초기화 전에 필요한 기존 데이터는 별도로 백업한다.
- 테이블과 컬럼에는 의미 있는 이름을 사용한다.
- 필수 데이터는 `NOT NULL`을 사용한다.
- 고유해야 하는 값은 `UNIQUE`로 제한한다.
- 참조 관계에는 `FOREIGN KEY`를 사용한다.
- 자주 조회하는 조건에는 필요한 인덱스를 추가한다.
- 외래 키 검사를 연결마다 활성화한다.

```python
connection.execute("PRAGMA foreign_keys = ON")
```

여러 SQL이 하나의 작업을 구성하면 하나의 트랜잭션으로 처리한다. 중간 실패 시 부분 저장이 남지 않게 한다.

### 스키마 버전

`app_metadata`의 `schema_version`은 현재 전체 스키마 기준 버전으로
관리한다. 스키마를 변경하면 최신 전체 생성문과 버전을 함께 갱신한다.

### SQLite 연결

- 연결은 필요한 작업 범위 안에서 열고 닫는다.
- 연결 객체를 전역으로 영구 공유하지 않는다.
- SQL 문자열에 사용자 입력을 직접 연결하지 않는다.
- 반드시 파라미터 바인딩을 사용한다.

```python
connection.execute(
    "SELECT id, name FROM courses WHERE id = ?",
    (course_id,),
)
```

다음 방식은 금지한다.

```python
connection.execute(
    f"SELECT * FROM courses WHERE id = {course_id}"
)
```

## `requirements.txt` 관리

Python 표준 라이브러리가 아닌 패키지를 새로 import하면 같은 변경에서 `requirements.txt`를 반드시 갱신한다.

예:

```python
import httpx
```

위 코드를 추가했다면:

```text
httpx==검증한_버전
```

을 `requirements.txt`에 추가한다.

반대로 더 이상 사용하지 않는 외부 라이브러리는 코드와 `requirements.txt`에서 함께 제거한다.

### 표준 라이브러리는 추가하지 않는다

다음은 Python 표준 라이브러리이므로 `requirements.txt`에 적지 않는다.

- `sqlite3`
- `pathlib`
- `json`
- `datetime`
- `typing`
- `os`

### 버전 규칙

- 프로젝트에서 실제 설치하고 검증한 버전을 명시한다.
- 같은 패키지를 중복 작성하지 않는다.
- 패키지 이름은 PyPI 배포 이름을 사용한다.
- 단순 import 성공뿐 아니라 실제 서버 실행을 확인한다.

의존성을 변경한 후에는 새 가상환경 기준으로 다음 절차를 확인한다.

```text
init_venv.bat
runserver.bat
```

## 검증

Python 파일은 `py_compile` 대신 AST 파싱으로 검증한다.

```python
from pathlib import Path
import ast

path = Path("main.py")
ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
```

API 변경 시 최소한 다음을 확인한다.

- 서버가 8000 포트에서 시작되는가
- 정상 요청이 약속된 상태 코드와 JSON을 반환하는가
- 잘못된 입력이 적절한 4xx를 반환하는가
- 존재하지 않는 데이터가 404를 반환하는가
- DB 변경이 실제 SQLite 파일에 반영되는가
- `init_db.py`를 다시 실행하면 기존 데이터가 삭제되고 빈 최신 스키마가
  생성되는가

## 배치 파일

- BAT 파일 위치는 `%~dp0`로 계산한다.
- `.venv`, `requirements.txt`, `main.py` 경로는 BAT 위치를 기준으로 한다.
- 공백이 포함된 경로를 고려해 경로를 따옴표로 감싼다.
- Windows `cmd.exe` 호환을 위해 ASCII 출력 문구와 CRLF 줄바꿈을 사용한다.
- `runserver.bat`은 `127.0.0.1:8000`에서 `main:app`을 실행한다.
