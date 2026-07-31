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
| 규모 | 백엔드 약 4,300줄(테스트 포함), 프런트 약 4,200줄 |

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
│  │  ├─ attendance_records.py    # 수강(출결) 기록 라우터
│  │  ├─ analytics.py             # 기간 기반 집계 조회 라우터(조회 전용)
│  │  ├─ worklists.py             # 운영 관리 대상 목록 라우터(조회 전용)
│  │  └─ checks.py                # 장부 정합성 점검 라우터(조회 전용)
│  ├─ database/                   # 데이터 계층 (여기에만 SQL이 존재)
│  │  ├─ db_connector.py          # ★ 유일한 저장소 인터페이스 (약 2,400줄)
│  │  ├─ connection.py            # SQLite 연결 생성 · PRAGMA · DB 파일 경로
│  │  └─ schema.py                # 전체 DDL(테이블/인덱스) + SCHEMA_VERSION
│  ├─ init_db.py                  # DB 파일 삭제 후 전체 스키마 재생성
│  ├─ init_data.py                # init_db + 테스트용 샘플 데이터 채우기
│  ├─ test/                       # 테스트 전용 디렉터리
│  │  ├─ conftest.py              # 공용 픽스처(client, ledger 빌더, 상대 날짜 도우미)
│  │  ├─ test_api.py              # 업무 API 통합 테스트
│  │  ├─ test_database.py         # 스키마 제약·삭제 정책 테스트
│  │  ├─ test_analytics.py        # 집계 API 테스트
│  │  ├─ test_worklists.py        # 관리 목록 API 테스트
│  │  └─ test_consistency.py      # 장부 정합성 점검 테스트
│  ├─ requirements.txt / pytest.ini
│  ├─ init_venv.bat               # .venv 생성 + 의존성 설치
│  ├─ runserver.bat               # 8000 포트 서버 실행
│  └─ local_database.db           # 실행 중 생성(Git 제외)
└─ frontend/
   ├─ AGENTS.md                   # 프런트 UX/디자인 지침
   ├─ index.html                  # 홈: 진입 카드 3개(정보 등록 · 사업자 대시보드 · Agent)
   ├─ pages/
   │  ├─ register.html            # 정보 등록: 아카데미 생성 폼 + 수강생 생성 폼
   │  ├─ dashboard.html           # ★ 사업자 운영 콘솔(개요·출결·수강생·수강권 종류·관리 대상·통계)
   │  └─ agent.html               # 수강권 관리 Agent: 역할 선택 → 계정 선택 → 대화
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
- 프런트엔드는 DB에 직접 접근하지 않으며, 화면 코드는 `CourseApi` 어댑터를 통해서만 통신한다. 화면에서 `fetch()`를 직접 호출하지 않는다.
- DB 제품을 바꿀 때 API 계약과 `api/` 코드는 그대로 두고 `db_connector.py` 구현만 교체하는 것이 설계 목표.
- 마이그레이션은 관리하지 않는다. 스키마 변경 = `schema.py` 수정 + `init_db.py` 재실행(**기존 데이터 전부 삭제**).
- 조회 API는 데이터를 변경하지 않는다. 완료·취소·복구 같은 상태 변경은 기존 전용 액션 API만 사용한다.

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
- **시간대 주의**: `created_at`/`updated_at` 은 SQLite `CURRENT_TIMESTAMP`라 **UTC**로 저장되고, `purchased_at`·`expire_date`·`scheduled_at` 등 애플리케이션이 기록하는 값은 **로컬 시각**이다. 등록일 기준 집계는 `datetime(created_at, 'localtime')`으로 변환해 비교한다(`db_connector.STUDENT_CREATED_LOCAL`).
- `app_metadata` 테이블에 `schema_version` 저장.
- 현재 스키마에는 **결석(NO_SHOW) 상태가 없다.** 예정 시각이 지난 `RESERVED`는 ‘미처리 예약’일 뿐 결석 확정이 아니다.
- 결제·환불 데이터가 없다. `price_snapshot` 합계는 ‘발급가 기준 합계’이며 매출이 아니다.

## 5. API 엔드포인트 전체 목록

모든 엔드포인트는 명시적 `operation_id`를 갖는다(향후 Agent Tool Calling에 그대로 매핑하기 위함).

### 5.1 시스템

| 메서드 | 경로 | operation_id | 설명 |
|---|---|---|---|
| GET | `/ping` | (없음) | 서버 생존 확인 |
| GET | `/api/health` | `check_health` | 서버 + DB 연결 상태 확인 |

### 5.2 업무 리소스

| 메서드 | 경로 | operation_id |
|---|---|---|
| GET / POST | `/api/academies` | `list_academies` / `create_academy` |
| GET / PATCH / DELETE | `/api/academies/{academy_id}` | `get_academy` / `update_academy` / `delete_academy` |
| GET | `/api/academies/{academy_id}/summary` | `get_academy_summary` |
| GET / POST | `.../pass-types` | `list_pass_types` / `create_pass_type` |
| GET / PATCH / DELETE | `.../pass-types/{pass_type_id}` | `get_pass_type` / `update_pass_type` / `delete_pass_type` |
| GET / POST | `.../students` | `list_students` / `create_student` |
| GET / PATCH / DELETE | `.../students/{student_id}` | `get_student` / `update_student` / `delete_student` |
| GET | `.../students/{student_id}/summary` | `get_student_summary` |
| GET | `.../students/{student_id}/available-passes` | `list_student_available_passes` |
| GET | `.../students/{student_id}/attendance-records` | `list_student_attendance_records` |
| GET / POST | `.../students/{student_id}/passes` | `list_student_passes` / `issue_student_pass` |
| GET / PATCH / DELETE | `.../passes/{student_pass_id}` | `get_student_pass` / `update_student_pass` / `delete_student_pass` |
| GET | `.../passes/{student_pass_id}/attendance-records` | `list_student_pass_attendance_records` |
| GET / POST | `.../attendance-records` | `list_attendance_records` / `create_attendance_reservation` |
| GET / PATCH | `.../attendance-records/{id}` | `get_attendance_record` / `update_attendance_record` |
| POST | `.../attendance-records/{id}/complete` | `complete_attendance` |
| POST | `.../attendance-records/{id}/cancel` | `cancel_attendance` |
| POST | `.../attendance-records/{id}/restore` | `restore_attendance` |

### 5.3 운영 분석 (`api/analytics.py`, 조회 전용)

| 경로 | operation_id | 주요 쿼리 |
|---|---|---|
| `GET .../analytics/dashboard` | `get_academy_dashboard` | `date_from`, `date_to` |
| `GET .../analytics/registrations` | `get_registration_analytics` | `date_from`, `date_to`, `group_by`(day/week/month) |
| `GET .../analytics/attendance` | `get_attendance_analytics` | `date_from`, `date_to`, `group_by` |
| `GET .../analytics/pass-types` | `get_pass_type_analytics` | `date_from`, `date_to`, `limit`, `offset`, `sort`, `order` |

집계 기준(계약):

- 기간 기본값은 **오늘을 포함한 최근 30일**. `date_from > date_to` 이면 `400 INVALID_DATE_RANGE`.
- 신규 수강생 = `students.created_at`(로컬 변환) 기준, 수강권 발급 = `student_passes.purchased_at` 기준, 수강 집계 = `attendance_records.scheduled_at` 기준.
- `series`는 데이터가 없는 구간도 0으로 채워 반환한다. 주 단위 키는 그 주의 월요일, 월 단위 키는 해당 월 1일.
- `previous_period`는 선택 기간과 같은 길이의 직전 기간. 직전 값이 0이면 `rate`는 **null**(0으로 나누지 않음).
- `dashboard.attendance.pending_past`는 기간과 무관한 전체 미처리 예약 수, `analytics/attendance.totals.pending_past`는 선택 기간 안의 미처리 수.
- `issued_price_total`은 `price_snapshot` 합계이며 매출이 아니다.

### 5.4 관리 대상 목록 (`api/worklists.py`, 조회 전용)

| 경로 | operation_id | 주요 쿼리 |
|---|---|---|
| `GET .../worklists/pending-attendance` | `list_pending_attendance` | `scheduled_before`(기본 현재), `scheduled_from`, 페이지·정렬 |
| `GET .../worklists/expiring-passes` | `list_expiring_passes` | `days`(0~365, 기본 14), `include_expired`, `remaining_only`, `expired_only` |
| `GET .../worklists/low-balance-passes` | `list_low_balance_passes` | `max_remaining`(기본 3), `available_only` |
| `GET .../worklists/reregistration-candidates` | `list_reregistration_candidates` | `max_remaining`, `expiring_within_days`, `recent_attendance_days` |

- `expired_only=true` + `remaining_only=true` = “만료됐지만 잔여 횟수가 남은 수강권”.
- `low-balance`의 `available_only=true`는 **만료 전** 수강권만이라는 뜻이며 잔여 0회도 포함한다.
- 재등록 후보는 수강생당 1건만 반환하고 `reasons` 배열에 사유 코드를 모두 담는다.

```text
LOW_REMAINING_SESSIONS          사용 가능한 수강권 잔여 합계 ≤ max_remaining
EXPIRING_SOON                   사용 가능한 수강권이 expiring_within_days 이내 만료
ALL_PASSES_EXHAUSTED            보유 수강권 잔여 합계가 0
EXPIRED_WITH_RECENT_ATTENDANCE  사용 가능한 수강권 없음 + 만료된 수강권 있음
                                + recent_attendance_days 이내 완료 수강 기록 있음
```

### 5.5 정합성 점검 (`api/checks.py`, 조회 전용)

| 경로 | operation_id |
|---|---|
| `GET .../checks/ledger-consistency` | `check_ledger_consistency` |

`expected_remaining_sessions = total_sessions + SUM(attendance_records.session_delta)` 를 저장값과 비교하고, 어긋난 항목만 `items`로 돌려준다. **자동 수정하지 않는다.**

### 5.6 공통 규약

- 목록 응답은 `{ "items": [...], "pagination": { limit, offset, total } }`.
- 쿼리: `limit`(1~100, 기본 20), `offset`, `sort`, `order`(asc/desc). 정렬 필드는 `db_connector.py`의 `*_SORT_FIELDS` 화이트리스트로 제한된다.
- 상태 코드: 조회 200 / 생성 201 / 삭제 204 / 잘못된 입력 400 / 없음 404 / 충돌 409 / 검증 실패 422.
- 예측 가능한 업무 오류(`main.py` 전역 핸들러):

```json
{ "error": { "code": "PASS_EXPIRED", "message": "…", "details": {} } }
```

주요 `code`: `ACADEMY_NOT_FOUND`, `STUDENT_NOT_FOUND`, `PASS_TYPE_NOT_FOUND`, `STUDENT_PASS_NOT_FOUND`, `ATTENDANCE_RECORD_NOT_FOUND`, `DUPLICATE_PASS_TYPE_NAME`, `DUPLICATE_STUDENT_PHONE`, `PASS_EXPIRED`, `INSUFFICIENT_REMAINING_SESSIONS`, `ATTENDANCE_ALREADY_COMPLETED`, `ATTENDANCE_ALREADY_CANCELLED`, `INVALID_ATTENDANCE_TRANSITION`, `STUDENT_PASS_HAS_REMAINING_SESSIONS`, `EMPTY_UPDATE`, `INVALID_SORT_FIELD`, `INVALID_DATE_RANGE`, `INVALID_GROUP_BY`, `DATABASE_UNAVAILABLE`.

Pydantic 검증 실패는 FastAPI 기본 형식 `{"detail":[...]}`로 나가며, 프런트의 `messageFromError()`가 두 형식을 모두 처리한다.

## 6. Agent Tool Calling을 위한 API 원칙

이번 단계에서 Gemini 연동이나 Tool 스키마는 만들지 않았지만, 신규 API는 그대로 Tool로 매핑할 수 있게 설계했다.

- **안정적인 이름**: 모든 엔드포인트에 명시적 `operation_id`(§5)를 부여했다. 경로가 바뀌어도 이름은 유지한다.
- **구조화된 입력만**: `지난달`, `곧 만료` 같은 자연어 기간을 받지 않는다. `date_from`, `date_to`, `days`, `max_remaining`처럼 구조화된 값만 받고, 의미는 OpenAPI `description`에 적어 둔다.
- **결정적인 출력**: 설명 문장 대신 숫자와 고정 코드(`reasons`, `status`)를 반환한다. 표시용 한국어 문장은 프런트엔드가 만든다.
- **부작용 분리**: 신규 API는 전부 조회 전용이고, 상태 변경은 기존 `complete`/`cancel`/`restore`/`issue` 액션 API만 담당한다.
- **오류 계약 유지**: 위 §5.6의 `{"error": {...}}` 형식을 그대로 쓴다.

## 7. 프런트엔드 구조

### 7.1 화면 이동

```text
index.html (홈)
   ├─→ pages/register.html    "정보 등록"
   ├─→ pages/dashboard.html   "사업자 대시보드"
   └─→ pages/agent.html       "Agent 페이지"
```

### 7.2 `pages/dashboard.html` — 사업자 운영 콘솔

상단에서 아카데미를 고르면(선택값은 `localStorage`의 `courseEnroll.v1.dashboard.academyId`에 저장) 7개 탭이 활성화된다. 탭은 처음 열릴 때만 데이터를 불러오고, 상태 변경 후에는 영향받는 탭만 다시 조회한다.

```text
아카데미 선택
   │
   ├─ 개요        기간 프리셋(오늘/7일/30일/이번 달/지난달/사용자 지정) + KPI 12종
   │                → analytics.dashboard()
   ├─ 오늘의 출결  오늘 예약 표 + 완료·취소·완료취소 + 예약 만들기
   │                → attendanceRecords.list() + studentPasses.get()(잔여·만료일)
   ├─ 미처리 예약  예정 시각이 지난 RESERVED 목록 + 완료·취소 + 페이지네이션
   │                → worklists.pendingAttendance()
   ├─ 수강생      이름·전화·이메일·활성·만료일 범위 검색 + 정렬 + 페이지네이션
   │                → students.list() → 상세 드로어
   ├─ 수강권 종류  상품 카드 목록 + 추가·수정·삭제 + ◀ ▶ 노출 순서 변경
   │                → passTypes.list/create/update/remove()
   ├─ 관리 대상    만료 예정(7/14/30일) · 잔여 부족(0/1/3회) · 만료+잔여 · 재등록 후보
   │                → worklists.*()
   └─ 통계        신규 등록 · 수강권 발급 · 수강 이용 + 장부 정합성 점검
                    → analytics.*(), checks.ledgerConsistency()
```

수강생 상세 드로어(`<dialog>`)는 기본 정보·요약·보유 수강권·최근 수강 기록·다음 예약을 한 번에 보여주고, 그 안에서 **정보 수정 / 수강권 발급 / 예약 만들기**를 수행한다. 발급이 끝나면 수강생 요약·보유 수강권·회원 만료일을 다시 조회한다.

화면 규칙:

- 상태 변경(완료·취소·복구) 전에는 항상 확인 대화상자를 띄우고, 잔여 횟수 변화(예: `5회 → 4회`)를 문장으로 보여준다. 복구는 사유 입력을 요구한다.
- 예약 생성 화면은 “예약해도 잔여 횟수는 줄지 않는다”를 명시한다.
- 과거 `RESERVED`는 ‘미처리 예약 · 결석 의심 · 출결 확인 필요’로만 부르고 결석으로 확정하지 않는다.
- `price_snapshot` 합계는 ‘발급가 기준 합계(실제 매출 아님)’로 표기한다.
- 수업명은 자유 입력이라 표기가 다르면 따로 집계된다는 도움말을 통계 화면에 둔다.
- 차트는 외부 라이브러리 없이 CSS 막대(`.bar-chart`)로 그린다. 숫자는 `Intl.NumberFormat('ko-KR')`, 날짜는 공통 포맷 함수를 사용한다.
- 모든 목록은 로딩·빈 데이터·오류 상태를 각각 표시하고, 오류 문구는 `CourseApi.messageFromError()`로 만든다.

### 7.3 `pages/register.html`

- 아카데미 생성 폼 → `academies.create()`
- 수강생 생성 폼 → `academies.list()`로 셀렉트를 채우고 `students.create()`

### 7.4 `pages/agent.html`

역할 선택(사업자/회원) → 아카데미·수강생 선택 → 대화 화면. 수강권 종류 관리는 **대시보드의 ‘수강권 종류’ 탭으로 옮겼고**, 이 페이지는 대화에만 집중한다. 채팅 입력창은 있으나 **백엔드가 없어 응답하지 않는다**(`// TODO: 백엔드 Agent API 연동 자리`).

### 7.5 `assets/api.js` — API 어댑터

`window.CourseApi` 하나만 노출한다. 공통 함수는 `apiRequest()`, `toQuery()`, `messageFromError()`, `codeFromError()`.

| 네임스페이스 | 메서드 |
|---|---|
| `academies` | list, create, get, update, remove, summary |
| `passTypes` | list, create, get, update, remove |
| `students` | list, create, get, update, remove, summary, availablePasses, attendanceRecords |
| `studentPasses` | list, create, get, update, remove, attendanceRecords |
| `attendanceRecords` | list, create, get, update, complete, cancel, restore |
| `analytics` | dashboard, registrations, attendance, passTypes |
| `worklists` | pendingAttendance, expiringPasses, lowBalancePasses, reregistrationCandidates |
| `checks` | ledgerConsistency |
| `health` | ping, check |

현재 백엔드의 모든 업무 엔드포인트가 어댑터로 감싸져 있다.

### 7.6 `assets/styles.css`

전 페이지 공용 단일 스타일시트. `:root` 디자인 토큰 → 공용 컴포넌트(`.btn`, `.input`, `.field`, `.form-status`) → 화면별 블록(`.role-card`, `.pass-card`, `.message`, `.chat-form`, 그리고 대시보드용 `.dash-bar`, `.tabs`, `.section`, `.kpi`, `.table`, `.badge`, `.bar-chart`, `.drawer`) → 720px 이하 반응형 순서로 구성. 클래스 네이밍은 BEM 유사(`block__element--modifier`).

## 8. 현재 구현 상태 / 남은 공백

구현 완료:

- 5개 리소스 REST CRUD + 요약/집계 + 수강 상태 전이(완료/취소/복구)와 잔여 횟수 정합성.
- 기간 기반 분석 4종, 관리 대상 목록 4종, 장부 정합성 점검 1종(모두 조회 전용).
- 화면: 아카데미·수강생 등록, **사업자 운영 대시보드 전체**(개요·오늘 출결·미처리·수강생 관리·수강권 발급·예약 생성·수강권 종류 관리·관리 대상·통계).
- `init_data.py`로 사업소 2곳 · 수강생 70명 · 수강 기록 약 500건 규모의 테스트 데이터를 한 번에 만들 수 있다.

미구현 / 공백:

1. **Agent 채팅 백엔드가 없다.** `agent.html`의 채팅은 화면에만 남아 있고 LLM 연동·의도 파악·Tool 호출 계층이 없다. 신규 조회 API는 Tool로 매핑할 준비만 끝난 상태다.
2. **회원(member) 역할 화면이 비어 있다.** 역할·계정 선택까지만 되고 본인 잔여/만료/이용 내역 화면이 없다(백엔드 API는 이미 있음).
3. **인증·권한이 없다.** ‘사업자/회원’은 화면상의 모드일 뿐 서버가 검증하지 않는다. 대시보드는 아카데미만 고르면 모든 데이터를 볼 수 있다.
4. 현재 스키마로 만들 수 없는 것: 결석(NO_SHOW) 확정, 실제 매출·결제·환불, 상담·연락 이력, 강사, 수업 종류 마스터.
5. 수업명 정규화가 없어 통계에서 같은 수업이 여러 항목으로 나뉠 수 있다.
6. 프런트엔드 자동화 테스트 환경이 없다(수동 확인 + 정적 검사로 대체).

## 9. 실행 방법

```text
backend/init_venv.bat                                    # 최초 1회
backend/.venv/Scripts/python.exe backend/init_db.py      # 빈 DB로 초기화(기존 데이터 삭제)
backend/.venv/Scripts/python.exe backend/init_data.py    # 초기화 + 테스트용 샘플 데이터
backend/runserver.bat                                    # 127.0.0.1:8000
frontend/runserver.bat                                   # 127.0.0.1:5173
backend/.venv/Scripts/python.exe -m pytest backend       # 테스트 37건
```

`init_data.py`는 `init_db.py`와 마찬가지로 **기존 DB를 삭제**한 뒤 아래 데이터를 만든다.
경로를 인자로 주면(`python init_data.py 다른경로.db`) 로컬 DB를 보존한 채 만들 수 있다.

| 항목 | 규모 |
|---|---|
| 아카데미 | 2곳(한빛 필라테스 / 그린 요가원) |
| 수강권 종류 | 아카데미당 4종(체험·기본·장기·개인) |
| 수강생 | 아카데미당 35명, 총 70명 |
| 발급된 수강권 | 74건 |
| 수강 기록 | 498건(완료 398 · 취소 18 · 미처리 22 · 오늘 예약 22 · 향후 예약 38) |

수강생은 코호트(신규 활성 / 곧 만료 / 잔여 부족 / 만료+잔여 / 만료+최근 수강 / 장기 / 일반 / 개인 레슨 / 체험 후 소진 / 체험 후 미등록 / 미처리 예약 보유)로 나뉘어 있어 대시보드의 모든 목록·지표와 재등록 후보 사유 코드 4종이 모두 채워진다. 난수 시드가 고정돼 있어 실행할 때마다 같은 데이터가 만들어진다.

업무 데이터는 전부 `db_connector` 공개 함수로 만들어 스냅샷·잔여 횟수·만료일 규칙이 실제와 동일하게 적용된다. 유일한 예외는 신규 등록 통계를 확인하기 위해 수강생 `created_at`을 과거로 되돌리는 초기화 전용 처리다(DB 기본값이라 공개 함수로 지정할 수 없다).
