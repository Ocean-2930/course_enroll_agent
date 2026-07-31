# Course Enroll Agent 개발 지침

## 적용 범위

이 파일은 `course_enroll_agent/` 전체에 적용되는 공통 지침이다.

하위 디렉터리에 별도의 `AGENTS.md`가 있으면 해당 디렉터리 작업에는 하위 지침을 함께 적용한다.

```text
course_enroll_agent/
├─ AGENTS.md
├─ docs/
│  └─ PROJECT_STRUCTURE.md
├─ frontend/
│  ├─ AGENTS.md
│  ├─ index.html
│  └─ runserver.bat
└─ backend/
   ├─ AGENTS.md
   ├─ main.py
   ├─ init_db.py
   ├─ api/
   │  ├─ router.py
   │  └─ 리소스별 API 모듈
   ├─ database/
   │  ├─ db_connector.py
   │  ├─ connection.py
   │  └─ schema.py
   ├─ requirements.txt
   ├─ init_venv.bat
   └─ runserver.bat
```

## 프로젝트 구성

- `frontend/`: 사용자 화면과 브라우저 상호작용
- `backend/`: FastAPI 서버와 SQLite 데이터 접근
- 프런트엔드 포트: `127.0.0.1:5173`
- 백엔드 포트: `127.0.0.1:8000`
- 업무 API prefix: `/api`
- API 문서: `/docs`, `/redoc`, `/openapi.json`

기존 `agents_lab_handoff` 프로젝트는 화면과 사용자 경험을 참고하기 위한 자료다. 기존 n8n, Supabase, Gemini, Groq 구조를 새 프로젝트의 백엔드 요구사항으로 간주하지 않는다.

## 공통 작성 규칙

- 사용자에게 보이는 문구와 프로젝트 문서는 한국어로 작성한다.
- 텍스트 파일은 UTF-8로 저장한다.
- 비밀키, 토큰, 비밀번호, 운영 URL은 소스 코드에 하드코딩하지 않는다.
- 생성 파일, 가상환경, SQLite DB, 캐시는 Git에 포함하지 않는다.
- 한 파일에 화면, 데이터 접근, API 처리 등 서로 다른 책임을 과도하게 모으지 않는다.
- 기존 인터페이스를 변경할 때는 프런트엔드와 백엔드의 영향을 함께 확인한다.

## 프로젝트 구조 문서

`docs/PROJECT_STRUCTURE.md`는 기획·설계 단계에서 프로젝트 전체를 파악하기 위한
요약 문서다. 파일 구성, 계층 경계, 데이터 모델, API 목록, 화면 흐름, 미구현
공백을 한곳에 모아둔다.

다음 변경이 발생하면 **같은 작업에서** 이 문서를 함께 갱신한다.

- 파일이나 디렉터리를 추가·삭제·이동했을 때
- API 엔드포인트, 요청·응답 계약, 오류 코드가 바뀌었을 때
- `database/schema.py`의 테이블·컬럼·제약조건이 바뀌었을 때
- 화면이 추가되거나 화면 간 이동 흐름이 바뀌었을 때
- `frontend/assets/api.js`의 어댑터 메서드가 늘거나 줄었을 때
- 미구현이던 기능을 구현했을 때(“현재 구현 상태 / 공백” 절 갱신)
- 실행 방법이나 계층 경계 규칙이 바뀌었을 때

문서와 코드가 어긋나면 코드가 기준이며, 어긋난 사실을 발견하면 그 자리에서
문서를 고친다.

## 프런트엔드와 백엔드의 경계

- 프런트엔드는 데이터베이스에 직접 접근하지 않는다.
- 프런트엔드는 FastAPI의 HTTP API만 호출한다.
- 백엔드는 UI 표시 방법을 결정하지 않는다.
- API 요청과 응답은 JSON을 기본으로 한다.
- API 기본 주소는 프런트엔드의 API 클라이언트 또는 환경 설정 한 곳에서 관리한다.
- API가 아직 구현되지 않은 기능은 프런트엔드에서 목 데이터로 표현할 수 있지만 실제 저장이나 동기화가 되는 것처럼 표시하지 않는다.

## API와 데이터베이스의 교체 경계

- `backend/api/`는 HTTP 요청 검증, 응답 모델, 상태 코드와 라우팅만
  담당한다.
- `backend/api/`와 `backend/main.py`에서는 SQLite 연결 객체를 만들거나
  SQL을 실행하지 않는다.
- 실행 중 데이터 조회·생성·수정·삭제와 트랜잭션은 반드시
  `backend/database/db_connector.py`의 공개 함수를 통해 수행한다.
- API 모듈은 `database.connection`이나 `sqlite3`를 직접 import하지 않는다.
- 정렬 허용 목록, 아카데미 소속 검증, 외래 키 관련 업무 오류도
  `db_connector.py` 안에서 처리한다.
- 향후 데이터베이스 제품을 변경할 때 API 함수와 요청·응답 계약은
  유지하고 `db_connector.py`의 공개 함수 구현만 교체하는 것을 원칙으로
  한다.
- DB 초기 생성 DDL은 `database/schema.py`, 연결의 SQLite 세부 설정은
  `database/connection.py`에 한정한다. 이 두 파일은 초기화·연결 인프라이며
  API가 직접 의존하지 않는다.

## 실행 방법

백엔드 최초 설정:

```text
backend/init_venv.bat
```

SQLite 초기화(기존 DB와 데이터 삭제 후 재생성):

```text
backend/.venv/Scripts/python.exe backend/init_db.py
```

백엔드 실행:

```text
backend/runserver.bat
```

프런트엔드 실행:

```text
frontend/runserver.bat
```

## 변경 완료 기준

- 변경한 Python 파일은 `py_compile` 대신 UTF-8로 읽어 `ast.parse()` 검증을 수행한다.
- 변경한 API는 정상 요청뿐 아니라 잘못된 입력과 실패 응답도 확인한다.
- DB 스키마 변경은 `backend/database/schema.py`의 전체 생성문에 반영한다.
- 외부 Python 라이브러리를 추가하거나 제거하면 `backend/requirements.txt`를 함께 갱신한다.
- 프런트엔드가 사용하는 API 계약이 변경되면 `frontend/AGENTS.md` 또는 별도 API 계약 문서도 갱신한다.
- 파일 구성, API, 스키마, 화면 흐름, 구현 상태가 바뀌면 `docs/PROJECT_STRUCTURE.md`를 함께 갱신한다.
- 배치 파일은 `%~dp0`를 기준으로 경로를 계산하고 Windows `cmd.exe`에서 실행 가능한 ASCII 문구와 CRLF 줄바꿈을 사용한다.
