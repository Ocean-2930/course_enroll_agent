# Course Enroll Agent — 프로젝트 구조 정리

> 이 문서는 기획·설계 단계에서 프로젝트 전체를 파악하기 위한 요약본이다.
> 파일 구조, 계층 경계, API 계약, 화면 흐름이 바뀌면 같은 변경에서 이 문서도 갱신한다.

## 1. 개요

수강권(회차권) 장부를 관리하는 로컬 웹 앱. **아카데미 → 수강권 종류 → 수강생 → 보유 수강권 → 수강(출결) 기록** 이 도메인의 축이다.

| 항목 | 내용 |
|---|---|
| 백엔드 | Python / FastAPI / SQLite (표준 `sqlite3`) · `127.0.0.1:8000` |
| 프런트엔드 | 빌드 도구 없는 순수 HTML + CSS + Vanilla JS · `127.0.0.1:5173` |
| 업무 API prefix | `/api` (그 외 `/ping`, `/docs`, `/openapi.json`) |
| 인증 | **없음** (로컬 단일 사용자 전제, 권한 개념 미구현) |
| 규모 | 백엔드 약 3,000줄, 프런트 약 2,200줄 |

## 2. 디렉터리 구조

```text
course_enroll_agent/
├─ AGENTS.md                      # 프로젝트 공통 개발 지침(아키텍처 규칙의 원본)
├─ docs/
│  └─ PROJECT_STRUCTURE.md        # 이 문서
├─ backend/
│  ├─ AGENTS.md                   # 백엔드 지침(API 추가 절차, DB 규칙)
│  ├─ main.py                     # FastAPI 앱 생성 · CORS · 전역 예외 처리 · /ping
│  ├─ api/                        # HTTP 계층 (SQL 없음)
│  │  ├─ router.py                # /api 루트 라우터 + /api/health
│  │  ├─ models.py                # Pydantic 요청/응답 모델 전부
│  │  ├─ common.py                # 공용 쿼리 타입(Limit/Offset/Order 등)
│  │  ├─ academies.py             # 아카데미 라우터
│  │  ├─ pass_types.py            # 수강권 "종류"(상품) 라우터
│  │  ├─ students.py              # 수강생 라우터
│  │  ├─ student_passes.py        # 수강생이 "보유한" 수강권 라우터
│  │  └─ attendance_records.py    # 수강(출결) 기록 라우터
│  ├─ database/                   # 데이터 계층 (여기에만 SQL이 존재)
│  │  ├─ db_connector.py          # ★ 유일한 저장소 인터페이스 (약 1,760줄)
│  │  ├─ connection.py            # SQLite 연결 생성 · PRAGMA · DB 파일 경로
│  │  └─ schema.py                # 전체 DDL(테이블/인덱스) + SCHEMA_VERSION
│  ├─ init_db.py                  # DB 파일 삭제 후 전체 스키마 재생성
│  ├─ test_api.py                 # API 통합 테스트(TestClient, 9건)
│  ├─ test_database.py            # db_connector 단위 테스트(8건)
│  ├─ requirements.txt / pytest.ini
│  ├─ init_venv.bat               # .venv 생성 + 의존성 설치
│  ├─ runserver.bat               # 8000 포트 서버 실행
│  └─ local_database.db           # 실행 중 생성(Git 제외)
└─ frontend/
   ├─ AGENTS.md                   # 프런트 UX/디자인 지침 (일부 내용은 현행 코드보다 낡음)
   ├─ index.html                  # 홈: 두 개의 진입 카드만 있는 허브
   ├─ pages/
   │  ├─ register.html            # 정보 등록: 아카데미 생성 폼 + 수강생 생성 폼
   │  └─ agent.html               # 수강권 관리 Agent: 역할 선택 → 계정 선택 → 관리/채팅
   ├─ assets/
   │  ├─ api.js                   # ★ 유일한 API 클라이언트(window.CourseApi)
   │  └─ styles.css               # 전체 공용 스타일 + 디자인 토큰(:root 변수)
   └─ runserver.bat               # 5173 포트 정적 서버
```

## 3. 계층과 호출 구조

### 3.1 전체 호출 경로 (요청 1건의 흐름)

```text
[브라우저 화면]  pages/*.html 안의 <script>
        │  (URL·헤더를 직접 모름. 어댑터만 호출)
        ▼
[API 어댑터]     assets/api.js  →  window.CourseApi.<리소스>.<동작>()
        │  fetch(API_BASE_URL + path)   ※ base URL은 이 파일 한 곳에서만 관리
        ▼  HTTP/JSON
[FastAPI 진입]   backend/main.py  (CORS, DatabaseError → JSON 변환)
        ▼
[라우팅]         api/router.py  →  api/<리소스>.py
        │  Pydantic 검증(models.py), 상태 코드 결정. SQL·sqlite3 사용 금지
        ▼
[저장소]         database/db_connector.py  (공개 함수 = 유일한 데이터 접근점)
        │  SQL, 소속 검증, 업무 오류(DatabaseError), 트랜잭션 전부 여기
        ▼
[연결/스키마]    database/connection.py (연결·PRAGMA) · database/schema.py (DDL)
        ▼
                 local_database.db (SQLite)
```

### 3.2 반드시 지켜지는 경계 규칙 (기획 시 전제)

- `api/*` 는 `database.db_connector` **만** 호출한다. `sqlite3`, `database.connection`, SQL 문자열을 직접 쓰지 않는다.
- 트랜잭션이 필요한 복합 작업은 `db_connector.py`의 **공개 함수 하나 안에서** 끝낸다. (예: 수강 완료 처리 = 기록 상태 변경 + 잔여 횟수 차감)
- 프런트엔드는 DB에 직접 접근하지 않으며, 화면 코드는 `CourseApi` 어댑터를 통해서만 통신한다.
- DB 제품을 바꿀 때 API 계약과 `api/` 코드는 그대로 두고 `db_connector.py` 구현만 교체하는 것이 설계 목표.
- 마이그레이션은 관리하지 않는다. 스키마 변경 = `schema.py` 수정 + `init_db.py` 재실행(**기존 데이터 전부 삭제**).

## 4. 데이터 모델 (`schema.py`, SCHEMA_VERSION = 4)

```text
academies (아카데미/사업장)
   │
   ├─< pass_types (수강권 종류 = 판매 상품)
   │        name, total_sessions, validity_days, price, sort_index
   │        UNIQUE(academy_id, name) · 화면 노출 순서는 sort_index
   │
   ├─< students (수강생)
   │        name, phone, email, memo, expire_date
   │        phone은 아카데미 내에서 UNIQUE(있을 때만)
   │        │
   │        └─< student_passes (수강생이 실제로 구매/보유한 수강권)
   │                 total_sessions, remaining_sessions,
   │                 purchased_at, started_at, expire_date,
   │                 *_snapshot (발급 시점의 종류명·가격·유효기간 복사본)
   │
   └─< attendance_records (수강/출결 기록)
            class_name, scheduled_at,
            status: RESERVED | COMPLETED | CANCELLED,
            session_delta: 0 | -1,
            student_name_snapshot, pass_type_name_snapshot
```

핵심 설계 포인트:

- **스냅샷 컬럼**: 수강권 종류가 수정·삭제돼도 과거 발급·수강 이력의 표기가 흔들리지 않도록 발급 시점 값을 복사해 둔다. (`pass_types` 삭제 시 `student_passes.pass_type_id` 는 `SET NULL`, 스냅샷은 유지)
- **잔여 횟수 정합성**: `remaining_sessions` 는 `0 <= remaining <= total` 을 DB CHECK로 강제. 상태와 차감량의 조합(`COMPLETED`면 반드시 `-1`)도 CHECK로 강제.
- **삭제 정책**: 아카데미 삭제 → 하위 전부 CASCADE. 수강생 삭제 → 보유 수강권 CASCADE, 수강 기록은 `SET NULL`(이력 보존).
- `app_metadata` 테이블에 `schema_version` 저장.

## 5. API 엔드포인트 전체 목록

시스템:

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/ping` | 서버 생존 확인 (`{"status":"ok"}`) |
| GET | `/api/health` | 서버 + DB 연결 상태 확인 |

아카데미 — `api/academies.py`:

| 메서드 | 경로 |
|---|---|
| GET / POST | `/api/academies` |
| GET / PATCH / DELETE | `/api/academies/{academy_id}` |
| GET | `/api/academies/{academy_id}/summary` (수강생·수강권·오늘 수강 집계) |

수강권 종류 — `api/pass_types.py`:

| 메서드 | 경로 |
|---|---|
| GET / POST | `/api/academies/{academy_id}/pass-types` |
| GET / PATCH / DELETE | `/api/academies/{academy_id}/pass-types/{pass_type_id}` |

수강생 — `api/students.py`:

| 메서드 | 경로 |
|---|---|
| GET / POST | `/api/academies/{academy_id}/students` (필터: name, phone, email, active, expire_from, expire_to) |
| GET / PATCH / DELETE | `.../students/{student_id}` |
| GET | `.../students/{student_id}/summary` |
| GET | `.../students/{student_id}/available-passes` (사용 가능한 보유 수강권) |
| GET | `.../students/{student_id}/attendance-records` |

보유 수강권 — `api/student_passes.py`:

| 메서드 | 경로 |
|---|---|
| GET / POST(발급) | `.../students/{student_id}/passes` |
| GET / PATCH / DELETE | `.../students/{student_id}/passes/{student_pass_id}` |
| GET | `.../passes/{student_pass_id}/attendance-records` |

수강 기록 — `api/attendance_records.py`:

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET / POST | `/api/academies/{academy_id}/attendance-records` | 예약 생성 |
| GET / PATCH | `.../attendance-records/{id}` | 예약 내용 수정 |
| POST | `.../{id}/complete` | 수강 완료 → 잔여 1회 차감 |
| POST | `.../{id}/cancel` | 예약 취소 |
| POST | `.../{id}/restore` | 완료 취소 → 잔여 1회 복구 |

공통 규약:

- 목록 응답은 `{ "items": [...], "pagination": {...} }` 형태. 쿼리: `limit`(1~100, 기본 20), `offset`, `sort`, `order`(asc/desc).
- 리소스별 정렬 허용 필드는 `db_connector.py` 상단의 `*_SORT_FIELDS` 화이트리스트로 제한된다.
- 상태 코드: 조회 200 / 생성 201 / 삭제 204 / 입력오류 400 / 없음 404 / 충돌 409.

오류 응답 형식(예측 가능한 업무 오류, `main.py`의 전역 핸들러가 생성):

```json
{ "error": { "code": "PASS_EXPIRED", "message": "…", "details": {} } }
```

주요 `code` 값: `ACADEMY_NOT_FOUND`, `STUDENT_NOT_FOUND`, `PASS_TYPE_NOT_FOUND`, `STUDENT_PASS_NOT_FOUND`, `ATTENDANCE_RECORD_NOT_FOUND`, `DUPLICATE_PASS_TYPE_NAME`, `DUPLICATE_STUDENT_PHONE`, `PASS_EXPIRED`, `INSUFFICIENT_REMAINING_SESSIONS`, `ATTENDANCE_ALREADY_COMPLETED`, `ATTENDANCE_ALREADY_CANCELLED`, `INVALID_ATTENDANCE_TRANSITION`, `STUDENT_PASS_HAS_REMAINING_SESSIONS`, `EMPTY_UPDATE`, `INVALID_SORT_FIELD`, `DATABASE_UNAVAILABLE`.

Pydantic 검증 실패는 FastAPI 기본 형식인 `{"detail":[...]}`로 나가며, 프런트의 `messageFromError()`가 두 형식을 모두 처리한다.

## 6. 프런트엔드 구조

### 6.1 화면 이동

```text
index.html (홈)
   ├─→ pages/register.html   "정보 등록"
   └─→ pages/agent.html      "수강권 관리 Agent"
```

### 6.2 각 페이지의 역할

**`index.html`** — 진입 카드 2개뿐인 허브. 로직 없음.

**`pages/register.html`** — 독립된 두 폼.

- 아카데미 생성 폼 → `CourseApi.academies.create()`
- 수강생 생성 폼 → 진입 시 `academies.list()` 로 셀렉트 채우고 → `students.create(academyId, payload)`
- 각 폼은 `idle / 검증 실패 / 전송 중 / 성공 / 실패` 상태를 직접 표시한다.

**`pages/agent.html`** — 하나의 카드 안에서 3단계 뷰를 `hidden` 토글로 전환한다.

```text
① #roleView    역할 선택 (owner=사업자 / member=회원)
       ↓ goToAccountStep()
② #accountView 아카데미 선택 (+ 회원이면 수강생 선택)  ← academies.list() / students.list()
       ↓ enterChat()
③ #chatView    실제 작업 화면
     ├─ .agent-scroll (스크롤하지 않는 컨테이너)
     │    ├─ #passPanel  수강권 정보 관리 — owner 역할일 때만 노출, 상단 고정
     │    │     └─ #passScroll  가로 스크롤 카드 목록
     │    │            · buildPassCard()  카드 표시 + 수정/삭제/◀▶ 순서 이동
     │    │            · buildPassForm()  생성·수정 공용 입력 카드
     │    │            · movePass()  이웃 카드와 sort_index 를 맞바꾸고 PATCH 2회
     │    └─ #messages   채팅 표시 영역 — 남는 높이를 채우고 내부에서만 세로 스크롤
     └─ .card__footer   #chatForm 입력창(Enter 전송, Shift+Enter 줄바꿈, 자동 높이)
```

- 상태는 모듈 스코프 변수 `currentRole`, `selected = { academy, student }` 로만 관리(프레임워크 없음).
- 역할별 문구·동작 차이는 상단의 `ROLES` 객체(badge/title/needsStudent/placeholder/greeting)에 모여 있다.
- **채팅은 아직 백엔드가 없다.** `form submit` 핸들러에 `// TODO: 백엔드 Agent API 연동 자리` 만 있고, 사용자 메시지를 화면에 추가할 뿐 응답이 없다.

### 6.3 `assets/api.js` — API 어댑터

`window.CourseApi` 하나만 노출. 내부 공통 함수는 `apiRequest()`(fetch + JSON + 오류 래핑), `toQuery()`(빈 값 생략 쿼리스트링), `messageFromError()`(오류 → 한국어 문구).

현재 노출된 메서드는 **백엔드 API의 일부만** 감싸고 있다.

| 어댑터 | 구현된 것 | 백엔드엔 있으나 어댑터에 **없는** 것 |
|---|---|---|
| `academies` | list, create | get, update, remove, summary |
| `passTypes` | list, create, update, remove | get |
| `students` | list, create | get, update, remove, summary, availablePasses, attendanceRecords |
| `studentPasses` | — | **전체 미구현** |
| `attendanceRecords` | — | **전체 미구현** |
| `health` | ping | `/api/health` |

### 6.4 `assets/styles.css`

전 페이지 공용 단일 스타일시트. `:root` 디자인 토큰(`--color-brand`, `--color-surface`, `--radius-card`, `--shadow-card` 등) → 공용 컴포넌트(`.btn`, `.input`, `.field`, `.form-status`) → 화면별 블록(`.role-card`, `.pass-panel`, `.pass-card`, `.message`, `.chat-form`) → 720px 이하 반응형 순서로 구성. 클래스 네이밍은 BEM 유사(`block__element--modifier`).

## 7. 현재 구현 상태 / 기획 시 알아야 할 공백

구현 완료:

- 5개 리소스에 대한 REST CRUD + 요약/집계 + 수강 상태 전이(완료/취소/복구)와 잔여 횟수 정합성 — **백엔드는 도메인이 상당히 완성돼 있다.**
- 화면: 아카데미·수강생 등록, 수강권 종류 관리(등록/수정/삭제/순서 변경).

미구현 / 공백:

1. **Agent 채팅에 백엔드가 없다.** 자연어 → 기능 실행 연결이 이 프로젝트의 다음 큰 축이며, LLM 연동·의도 파악·도구 호출 설계가 아직 전혀 없다.
2. **회원(member) 역할 화면이 비어 있다.** 역할 선택·계정 선택까지만 되고, 잔여 횟수·만료일·사용 내역 조회 UI가 없다(백엔드 API `.../summary`, `available-passes`, `attendance-records` 는 이미 존재).
3. **보유 수강권 발급 / 수강 기록(예약·완료·취소) UI가 전혀 없다.** 백엔드 API만 있고 화면과 어댑터가 없다 — 기능 대비 화면의 최대 공백 지점.
4. 인증·권한·다중 사용자 개념 없음. "사업자/회원" 은 화면상의 모드 전환일 뿐 서버가 검증하지 않는다.
5. 대시보드/리포트 화면 없음(`/summary` API는 있으나 소비처가 없다).
6. `frontend/AGENTS.md` 는 "확정된 API는 `/ping` 하나" 라고 적혀 있어 현재 코드보다 낡았다. 지침 문서를 근거로 판단할 때 주의.

## 8. 실행 방법

```text
backend/init_venv.bat                                   # 최초 1회
backend/.venv/Scripts/python.exe backend/init_db.py     # DB 초기화(기존 데이터 삭제)
backend/runserver.bat                                   # 127.0.0.1:8000
frontend/runserver.bat                                  # 127.0.0.1:5173
backend/.venv/Scripts/python.exe -m pytest backend      # 테스트 17건
```
