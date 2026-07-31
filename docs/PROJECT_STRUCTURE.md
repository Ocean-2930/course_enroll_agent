# Course Enroll Agent — 프로젝트 구조 정리

> 이 문서는 기획·설계 단계에서 프로젝트 전체를 파악하기 위한 요약본이다.
> 파일 구조, 계층 경계, API 계약, 화면 흐름이 바뀌면 같은 변경에서 이 문서도 갱신한다.
> 사업자·수강생이 실제로 어떤 UI를 쓰고 어떤 순서로 움직이는지는 [UI_FLOWS.md](UI_FLOWS.md)에 따로 정리했다.

## 1. 개요

수강권(회차권) 장부를 관리하는 로컬 웹 앱. **아카데미 → 수강권 종류 → 수강생 → 보유 수강권 → 수강(출결) 기록** 이 도메인의 축이다.

| 항목 | 내용 |
|---|---|
| 백엔드 | Python / FastAPI / SQLite (표준 `sqlite3`) · `127.0.0.1:8000` |
| 프런트엔드 | 빌드 도구 없는 순수 HTML + CSS + Vanilla JS · `127.0.0.1:5173` |
| 업무 API prefix | `/api` (그 외 `/ping`, `/docs`, `/openapi.json`) |
| 인증 | **없음** (로컬 단일 사용자 전제, 권한 개념 미구현) |
| 규모 | 백엔드 약 6,000줄(테스트 포함), 프런트 약 6,000줄 |

## 2. 디렉터리 구조

```text
course_enroll_agent/
├─ AGENTS.md                      # 프로젝트 공통 개발 지침(아키텍처 규칙의 원본)
├─ docs/
│  ├─ PROJECT_STRUCTURE.md        # 이 문서
│  └─ UI_FLOWS.md                 # 사업자·수강생 화면 안내와 이용 흐름
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
│  │  ├─ attendance_records.py    # 수강(출결) 기록 · 체크인 · 퇴실 라우터
│  │  ├─ inquiries.py             # 아카데미(사업자) 문의 라우터
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
│  │  ├─ test_consistency.py      # 장부 정합성 점검 테스트
│  │  ├─ test_member_portal.py    # 구매·삭제·예약·체크인·퇴실 테스트
│  │  └─ test_inquiries.py        # 문의 API 테스트
│  ├─ requirements.txt / pytest.ini
│  ├─ init_venv.bat               # .venv 생성 + 의존성 설치
│  ├─ runserver.bat               # 8000 포트 서버 실행
│  └─ local_database.db           # 실행 중 생성(Git 제외)
└─ frontend/
   ├─ AGENTS.md                   # 프런트 UX/디자인 지침
   ├─ index.html                  # 홈: 진입 카드 3개(정보 등록 · 사업자 대시보드 · Agent)
   ├─ pages/
   │  ├─ register.html            # 정보 등록: 아카데미 생성 폼 + 수강생 생성 폼
   │  ├─ dashboard.html           # ★ 사업자 운영 콘솔(개요·출결·수강생·수강권 종류·문의·통계)
   │  ├─ member.html              # ★ 회원 포털(홈·수강권·예약·출석/퇴실·문의)
   │  └─ agent.html               # 역할 선택 → 계정 선택 → (회원은 포털로 이동)
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

## 4. 데이터 모델 (`schema.py`, SCHEMA_VERSION = 5)

```text
academies (아카데미/사업장)
   │
   ├─< pass_types (수강권 종류 = 판매 상품)
   │        name, total_sessions, validity_days, price, sort_index,
   │        session_duration_minutes (1회 수업 시간, 기본 60, > 0)
   │        UNIQUE(academy_id, name) · 화면 노출 순서는 sort_index
   │
   ├─< students (수강생)
   │        name, phone, email, memo, expire_date
   │        phone은 아카데미 내에서 UNIQUE(있을 때만)
   │        │
   │        └─< student_passes (수강생이 실제로 구매/보유한 수강권)
   │                 total_sessions, remaining_sessions,
   │                 purchased_at, started_at, expire_date,
   │                 *_snapshot (구매 시점의 종류명·가격·유효기간·
   │                             session_duration_minutes 복사본)
   │
   ├─< attendance_records (수강/출결 기록)
   │        class_name, scheduled_at, scheduled_end_at,
   │        status: RESERVED | CHECKED_IN | COMPLETED | CANCELLED,
   │        session_delta: 0 | -1,
   │        checked_in_at, checked_out_at, completed_at, cancelled_at,
   │        student_name_snapshot, pass_type_name_snapshot
   │
   └─< inquiries (1:1 문의)
            category(9종), title, status: OPEN | ANSWERED | CLOSED,
            student_name_snapshot, related_student_pass_id,
            related_attendance_record_id, closed_at
            │
            └─< inquiry_messages
                     sender_type: STUDENT | ACADEMY, message, created_at
```

핵심 설계 포인트:

- **스냅샷 컬럼**: 수강권 종류가 수정·삭제돼도 과거 발급·수강 이력의 표기가 흔들리지 않도록 발급 시점 값을 복사해 둔다. (`pass_types` 삭제 시 `student_passes.pass_type_id` 는 `SET NULL`, 스냅샷은 유지)
- **잔여 횟수 정합성**: `remaining_sessions` 는 `0 <= remaining <= total` 을 DB CHECK로 강제. 상태와 차감량의 조합(`COMPLETED`면 반드시 `-1`)도 CHECK로 강제.
- **수업 시간과 종료 시각**: 예약 종료 시각(`scheduled_end_at`)은 클라이언트가 보내지 않고 `student_passes.session_duration_minutes_snapshot` 으로 서버가 계산한다. 종류를 수정·삭제해도 이미 구매한 수강권의 수업 시간은 바뀌지 않는다.
- **상태와 시각 규칙**(DB CHECK로 강제):

```text
RESERVED    delta 0  · checked_in_at NULL       · checked_out_at NULL
CHECKED_IN  delta 0  · checked_in_at NOT NULL   · checked_out_at NULL
COMPLETED   delta -1 · checked_in_at NOT NULL   · checked_out_at NOT NULL
CANCELLED   delta 0  · checked_out_at NULL      · cancelled_at NOT NULL
```

- **삭제 정책**: 아카데미 삭제 → 하위 전부 CASCADE(문의·문의 메시지 포함). 수강생 삭제 → 보유 수강권 CASCADE, 수강 기록·문의는 `SET NULL`(이름 스냅샷으로 이력 보존). 문의 삭제 → 메시지 CASCADE. 보유 수강권 삭제 → 수강 기록과 문의의 참조만 `SET NULL`.
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
| POST | `.../attendance-records/{id}/check-in` | `check_in_attendance` |
| POST | `.../attendance-records/{id}/check-out` | `check_out_attendance` |
| POST | `.../attendance-records/{id}/complete` | `complete_attendance` |
| POST | `.../attendance-records/{id}/cancel` | `cancel_attendance` |
| POST | `.../attendance-records/{id}/restore` | `restore_attendance` |

수강권 구매·삭제와 예약 생성·취소는 위 업무 API를 그대로 쓴다. 회원 화면에서 부르는 이름과 실제 `operation_id` 는 다음과 같이 대응한다.

| 회원 동작 | 사용하는 operation_id |
|---|---|
| 수강권 구매 | `issue_student_pass` (POST `.../students/{id}/passes`) |
| 구매한 수강권 삭제 | `delete_student_pass` |
| 수강 예약 | `create_attendance_reservation` |
| 예약 취소 | `cancel_attendance` |

### 5.2.1 회원 포털 전용 (`api/students.py`)

| 메서드 | 경로 | operation_id |
|---|---|---|
| GET | `.../students/{student_id}/portal-summary` | `get_student_portal_summary` |
| GET | `.../students/{student_id}/reservations` | `list_student_reservations` |
| GET / POST | `.../students/{student_id}/inquiries` | `list_student_inquiries` / `create_student_inquiry` |
| GET | `.../students/{student_id}/inquiries/{inquiry_id}` | `get_student_inquiry` |
| POST | `.../inquiries/{inquiry_id}/messages` | `add_student_inquiry_message` |
| POST | `.../inquiries/{inquiry_id}/close` | `close_student_inquiry` |

### 5.2.2 사업자 문의 (`api/inquiries.py`)

| 메서드 | 경로 | operation_id |
|---|---|---|
| GET | `/api/academies/{academy_id}/inquiries` | `list_academy_inquiries` |
| GET | `.../inquiries/{inquiry_id}` | `get_academy_inquiry` |
| POST | `.../inquiries/{inquiry_id}/messages` | `add_academy_inquiry_message` |
| POST | `.../inquiries/{inquiry_id}/close` | `close_academy_inquiry` |

동작 규칙:

- **구매**: 결제 없이 `student_passes` 행을 만들고 상품 스냅샷(수업 시간 포함)을 복사한 뒤 `students.expire_date` 를 갱신한다. 주문·결제 테이블은 없다.
- **삭제**: 잔여 횟수와 무관하게 물리 삭제하고, 남은 수강권의 최대 만료일로 `students.expire_date` 를 다시 계산한다(없으면 NULL). 수강 기록은 지우지 않고 참조만 끊는다.
- **체크인**: `RESERVED → CHECKED_IN`, 차감 없음. 중복은 409 `ATTENDANCE_ALREADY_CHECKED_IN`.
- **퇴실**: `CHECKED_IN → COMPLETED`, 잔여 1회 차감. 상태 변경과 차감이 한 트랜잭션이라 중복 요청이 두 번 차감되지 않는다.
- **사업자 완료**: `RESERVED`·`CHECKED_IN` 모두 허용. 예약에서 바로 완료하면 완료 시각을 체크인 시각으로도 기록한다.
- **복구**: `COMPLETED → CANCELLED`, 잔여 +1, `checked_in_at`·`checked_out_at`·`completed_at` 을 모두 비운다.
- **체크인 후 취소 불가**: `CHECKED_IN` 상태에서 취소 API는 409 를 반환하고 문의로 안내한다.
- **문의 상태 전이**: 생성 `OPEN` → 사업자 답변 `ANSWERED` → 회원 추가 메시지 `OPEN` → 종료 `CLOSED`(양쪽 모두 메시지 추가 불가).

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

주요 `code`: `ACADEMY_NOT_FOUND`, `STUDENT_NOT_FOUND`, `PASS_TYPE_NOT_FOUND`, `STUDENT_PASS_NOT_FOUND`, `ATTENDANCE_RECORD_NOT_FOUND`, `INQUIRY_NOT_FOUND`, `DUPLICATE_PASS_TYPE_NAME`, `DUPLICATE_STUDENT_PHONE`, `PASS_EXPIRED`, `INSUFFICIENT_REMAINING_SESSIONS`, `ATTENDANCE_ALREADY_COMPLETED`, `ATTENDANCE_ALREADY_CANCELLED`, `ATTENDANCE_ALREADY_CHECKED_IN`, `ATTENDANCE_NOT_RESERVED`, `ATTENDANCE_NOT_CHECKED_IN`, `INVALID_ATTENDANCE_TRANSITION`, `INQUIRY_CLOSED`, `INVALID_INQUIRY_CATEGORY`, `EMPTY_INQUIRY_MESSAGE`, `EMPTY_INQUIRY_TITLE`, `STUDENT_PASS_OWNER_MISMATCH`, `ATTENDANCE_RECORD_OWNER_MISMATCH`, `EMPTY_UPDATE`, `INVALID_SORT_FIELD`, `INVALID_DATE_RANGE`, `INVALID_GROUP_BY`, `DATABASE_UNAVAILABLE`.

`STUDENT_PASS_HAS_REMAINING_SESSIONS` 는 삭제 제한이 사라지면서 더 이상 발생하지 않는다.

Pydantic 검증 실패는 FastAPI 기본 형식 `{"detail":[...]}`로 나가며, 프런트의 `messageFromError()`가 두 형식을 모두 처리한다.

## 6. Agent Tool Calling을 위한 API 원칙

이번 단계에서 Gemini 연동이나 Tool 스키마는 만들지 않았지만, 신규 API는 그대로 Tool로 매핑할 수 있게 설계했다.

- **안정적인 이름**: 모든 엔드포인트에 명시적 `operation_id`(§5)를 부여했다. 경로가 바뀌어도 이름은 유지한다.
- **구조화된 입력만**: `지난달`, `곧 만료` 같은 자연어 기간을 받지 않는다. `date_from`, `date_to`, `days`, `max_remaining`처럼 구조화된 값만 받고, 의미는 OpenAPI `description`에 적어 둔다.
- **결정적인 출력**: 설명 문장 대신 숫자와 고정 코드(`reasons`, `status`)를 반환한다. 표시용 한국어 문장은 프런트엔드가 만든다.
- **부작용 분리**: 조회 API는 데이터를 바꾸지 않는다. 구매·삭제·예약·취소·체크인·퇴실·문의는 각각 별도 엔드포인트이며, 하나의 엔드포인트가 상황에 따라 다른 변경을 하지 않는다.
- **서버가 계산하는 값은 받지 않는다**: `scheduled_end_at`, `status`, `session_delta`, `checked_in_at`, `checked_out_at`, `completed_at`, `remaining_sessions`, 수강권 스냅샷, 문의 `sender_type` 은 요청 본문에 넣을 수 없다(`extra="forbid"` 로 거부).
- **오류 계약 유지**: 위 §5.6의 `{"error": {...}}` 형식을 그대로 쓴다.

## 7. 프런트엔드 구조

### 7.1 화면 이동

```text
index.html (홈) — 진입 카드 4개(Agent 페이지가 마지막)
   ├─→ pages/register.html    "정보 등록"
   ├─→ pages/dashboard.html   "사업자 대시보드"
   ├─→ pages/member.html      "회원 포털"
   └─→ pages/agent.html       "Agent 페이지" (역할 선택 → 대화 화면)
```

회원 포털 진입은 **홈의 ‘회원 포털’ 카드 하나뿐이다.** 쿼리 파라미터 없이 열리므로 포털이 먼저 아카데미·회원 선택 화면을 보여주고, 선택하면 `member.html?academy_id=..&student_id=..` 로 다시 연다. `agent.html` 은 역할별 대화 화면만 담당하며 포털로 이동하지 않는다.

회원 포털 URL 의 ID 는 **로그인이 아니라 화면에서 고른 값**이다. 인증이 없으므로 다른 사람의 ID 를 넣으면 그대로 열린다. 실제 서비스로 쓰기 전에 인증과 권한 검증이 반드시 필요하다.

### 7.2 `pages/dashboard.html` — 사업자 운영 콘솔

상단에서 아카데미를 고르면(선택값은 `localStorage`의 `courseEnroll.v1.dashboard.academyId`에 저장) 8개 탭이 활성화된다. 탭은 처음 열릴 때만 데이터를 불러오고, 상태 변경 후에는 영향받는 탭만 다시 조회한다.

```text
아카데미 선택
   │
   ├─ 개요        ① 월간 수강 일정 달력(맨 위) → attendanceRecords.list()
   │                   날짜 칸마다 예약·완료·취소 건수, 오늘 칸에는 '오늘' 배지.
   │                   날짜를 누르면 아래에 그날 일정과 완료·취소·복구 버튼.
   │                ② 기간 프리셋(오늘/7일/30일/이번 달/지난달/사용자 지정) + KPI 12종
   │                   → analytics.dashboard()
   ├─ 오늘의 출결  오늘 예약 표 + 완료·취소·완료취소 + 예약 만들기
   │                → attendanceRecords.list() + studentPasses.get()(잔여·만료일)
   ├─ 미처리 예약  예정 시각이 지난 RESERVED 목록 + 완료·취소 + 페이지네이션
   │                → worklists.pendingAttendance()
   ├─ 수강생      이름·전화·이메일·활성·만료일 범위 검색 + 정렬 + 페이지네이션
   │                → students.list() → 상세 드로어
   ├─ 수강권 종류  상품 카드 목록 + 추가·수정·삭제 + ◀ ▶ 노출 순서 변경
   │                (1회 수업 시간 포함) → passTypes.list/create/update/remove()
   ├─ 문의        회원 문의 목록 + 상세 드로어에서 답변 등록·종료
   │                → inquiries.listForAcademy/getForAcademy/addAcademyMessage/closeForAcademy()
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
- 차트와 달력은 외부 라이브러리 없이 CSS 그리드·막대(`.calendar__grid`, `.bar-chart`)로 그린다. 숫자는 `Intl.NumberFormat('ko-KR')`, 날짜는 공통 포맷 함수를 사용한다.
- 달력의 날짜 칸은 `<button>`이라 키보드로 이동·선택할 수 있고, 오늘 날짜는 배지와 색으로, 선택한 날짜는 테두리로 구분한다. 날짜 제목은 오늘이면 `오늘 · 2026년 7월 31일 (금)` 처럼 표시한다.
- 목록 API의 `limit` 상한이 100이라, 달력은 한 달치를 나눠 받아 합친다(최대 10회).
- 모든 목록은 로딩·빈 데이터·오류 상태를 각각 표시하고, 오류 문구는 `CourseApi.messageFromError()`로 만든다.

### 7.3 `pages/member.html` — 회원 포털

홈의 ‘회원 포털’ 카드로만 들어온다. `academy_id`·`student_id` 가 없으면 아카데미·회원 선택 화면(`#pickerSection`)을 먼저 보여주고 탭을 숨긴다. 선택 후에는 5개 탭으로 구성한다.

```text
홈          잔여 횟수·사용 가능 수강권·가장 가까운 만료일·오늘 일정·답변 대기 문의 KPI
              현재 체크인 중인 수업(퇴실 버튼)과 다음 예약(출석·취소 버튼), 최근 이용 내역
              → students.portalSummary()
수강권      구매 가능한 상품 카드(1회 수업 시간·가격 표시) + 확인 모달 후 구매
              내 수강권 카드(잔여 막대·구매일·만료일·수업 시간) + 삭제(경고 모달)
              → passTypes.list(), studentPasses.create/list/remove()
예약        예약 폼(수강권·수업명·시작 일시·메모, 선택 시 잔여·만료·예상 종료 시각 안내)
              내 예약 목록 + 상태 칩 필터 + 출석·취소 버튼
              → students.availablePasses(), attendanceRecords.create(), reservations.list()
출석·퇴실   아직 처리되지 않은 예약(체크인 중을 맨 위로) + 출석·퇴실 버튼
              → reservations.list({upcoming_only:true}), attendanceRecords.checkIn/checkOut()
문의        문의 작성(유형·제목·내용·관련 수강권·관련 예약) + 내 문의 목록
              상세 드로어에서 대화 스레드 확인·추가 메시지·문의 종료
              → inquiries.*ForStudent()
```

화면 규칙:

- 구매·삭제·출석·퇴실·문의 종료처럼 되돌리기 어려운 동작은 모두 확인 모달을 거친다. 구매 모달은 회차·유효기간·수업 시간·가격과 "별도 결제 없이 즉시 등록" 안내를, 삭제 모달은 "남은 횟수와 관계없이 삭제되고 수강 기록은 유지된다"를 보여준다.
- 퇴실 확인에는 "수강권 1회가 차감됩니다"를 명시하고, 처리 중에는 버튼을 잠가 중복 제출을 막는다.
- 예상 종료 시각은 화면에서 미리 계산해 보여주되, 저장되는 값은 서버가 계산한 `scheduled_end_at` 이다.
- 원본 상품이 삭제된 수강권은 스냅샷 이름으로 표시하고 "원본 상품이 삭제된 수강권" 안내를 붙인다.

### 7.4 `pages/register.html`

- 아카데미 생성 폼 → `academies.create()`
- 수강생 생성 폼 → `academies.list()`로 셀렉트를 채우고 `students.create()`

### 7.5 `pages/agent.html`

역할 선택(사업자/회원) → 아카데미·수강생 선택 → 역할별 대화 화면. 수강권 종류 관리는 대시보드로, 회원 기능은 회원 포털로 옮겼고 이 페이지에서 포털로 이동하지는 않는다. 채팅 입력창은 있으나 **백엔드가 없어 응답하지 않는다**(`// TODO: 백엔드 Agent API 연동 자리`).

### 7.6 `assets/api.js` — API 어댑터

`window.CourseApi` 하나만 노출한다. 공통 함수는 `apiRequest()`, `toQuery()`, `messageFromError()`, `codeFromError()`.

| 네임스페이스 | 메서드 |
|---|---|
| `academies` | list, create, get, update, remove, summary |
| `passTypes` | list, create, get, update, remove |
| `students` | list, create, get, update, remove, summary, availablePasses, attendanceRecords, portalSummary |
| `studentPasses` | list, create, get, update, remove, attendanceRecords |
| `reservations` | list |
| `attendanceRecords` | list, create, get, update, complete, cancel, restore, checkIn, checkOut |
| `inquiries` | listForStudent, createForStudent, getForStudent, addStudentMessage, closeForStudent, listForAcademy, getForAcademy, addAcademyMessage, closeForAcademy |
| `analytics` | dashboard, registrations, attendance, passTypes |
| `worklists` | pendingAttendance, expiringPasses, lowBalancePasses, reregistrationCandidates |
| `checks` | ledgerConsistency |
| `health` | ping, check |

현재 백엔드의 모든 업무 엔드포인트가 어댑터로 감싸져 있다.

### 7.7 `assets/styles.css`

전 페이지 공용 단일 스타일시트. `:root` 디자인 토큰 → 공용 컴포넌트(`.btn`, `.input`, `.field`, `.form-status`) → 화면별 블록(`.role-card`, `.pass-card`, `.message`, `.chat-form`, 대시보드용 `.dash-bar`, `.tabs`, `.section`, `.kpi`, `.table`, `.badge`, `.bar-chart`, `.calendar-day`, `.drawer`, 회원 포털용 `.portal-bar`, `.product-card`, `.owned-card`, `.reservation-card`, `.thread`) → 720px 이하 반응형 순서로 구성. 클래스 네이밍은 BEM 유사(`block__element--modifier`).

## 8. 현재 구현 상태 / 남은 공백

구현 완료:

- 5개 리소스 REST CRUD + 요약/집계 + 수강 상태 전이(예약·체크인·퇴실·완료·취소·복구)와 잔여 횟수 정합성.
- 기간 기반 분석 4종, 관리 대상 목록 4종, 장부 정합성 점검 1종(모두 조회 전용).
- 1:1 문의(회원 등록·추가 메시지·종료, 사업자 답변·종료).
- 화면: 아카데미·수강생 등록, **사업자 운영 대시보드 전체**, **회원 포털 전체**(홈·수강권 구매/삭제·예약·출석/퇴실·문의).
- `init_data.py`로 사업소 2곳 · 수강생 70명 · 수강 기록 약 500건 · 문의 12건 규모의 테스트 데이터를 한 번에 만들 수 있다.

미구현 / 공백(의도적으로 만들지 않은 것 포함):

1. **인증·권한이 없다.** 회원 포털은 URL 의 `student_id` 로 대상을 정할 뿐 서버가 본인 여부를 검증하지 않는다. 실제 서비스 전 반드시 필요하다.
2. **결제가 없다.** ‘수강권 구매’는 결제 없이 `student_passes` 행을 만드는 동작이고, 주문·결제·환불·쿠폰 테이블이 없다. 삭제도 환불이 아니라 물리 삭제다.
3. **일정 중복을 검사하지 않는다.** 같은 회원이 같은 시간에 여러 예약을 잡을 수 있고, 강사·강의실·정원·예약 오픈 시간·수업과 수강권의 호환성도 검사하지 않는다. 수업 시간표 테이블 자체가 없다.
4. **체크인 가능 시간 제한이 없다.** 예약이 `RESERVED` 이면 예정일 전후 어느 때나 체크인할 수 있다. QR 체크인·자동 퇴실도 없다.
5. **Agent 채팅 백엔드가 없다.** `agent.html` 의 채팅은 화면만 있고 LLM 연동·의도 파악·Tool 호출 계층이 없다. API 는 Tool 매핑 준비만 끝난 상태다.
6. 현재 스키마로 만들 수 없는 것: 결석(NO_SHOW) 확정, 실제 매출, 상담·연락 이력, 강사, 수업 종류 마스터, 문의 파일 첨부, 알림(푸시·문자·이메일).
7. 수업명 정규화가 없어 통계에서 같은 수업이 여러 항목으로 나뉠 수 있다.
8. 프런트엔드 자동화 테스트 환경이 없다(수동 확인 + 정적 검사로 대체).

## 9. 실행 방법

```text
backend/init_venv.bat                                    # 최초 1회
backend/.venv/Scripts/python.exe backend/init_db.py      # 빈 DB로 초기화(기존 데이터 삭제)
backend/.venv/Scripts/python.exe backend/init_data.py    # 초기화 + 테스트용 샘플 데이터
backend/runserver.bat                                    # 127.0.0.1:8000
frontend/runserver.bat                                   # 127.0.0.1:5173
backend/.venv/Scripts/python.exe -m pytest backend       # 테스트 62건
```

`init_data.py`는 `init_db.py`와 마찬가지로 **기존 DB를 삭제**한 뒤 아래 데이터를 만든다.
경로를 인자로 주면(`python init_data.py 다른경로.db`) 로컬 DB를 보존한 채 만들 수 있다.

| 항목 | 규모 |
|---|---|
| 아카데미 | 2곳(한빛 필라테스 / 그린 요가원) |
| 수강권 종류 | 아카데미당 4종(체험·기본·장기·개인) |
| 수강생 | 아카데미당 35명, 총 70명 |
| 발급된 수강권 | 74건 |
| 수강 기록 | 508건(완료 398 · 취소 18 · 미처리 22 · 체크인 중 10 · 오늘 예약 22 · 향후 예약 38) |
| 문의 | 12건 / 메시지 20건(OPEN · ANSWERED · CLOSED 모두 포함) |

수강생은 코호트(신규 활성 / 곧 만료 / 잔여 부족 / 만료+잔여 / 만료+최근 수강 / 장기 / 일반 / 개인 레슨 / 체험 후 소진 / 체험 후 미등록 / 미처리 예약 보유)로 나뉘어 있어 대시보드의 모든 목록·지표와 재등록 후보 사유 코드 4종이 모두 채워진다. 난수 시드가 고정돼 있어 실행할 때마다 같은 데이터가 만들어진다.

업무 데이터는 전부 `db_connector` 공개 함수로 만들어 스냅샷·잔여 횟수·만료일 규칙이 실제와 동일하게 적용된다. 유일한 예외는 신규 등록 통계를 확인하기 위해 수강생 `created_at`을 과거로 되돌리는 초기화 전용 처리다(DB 기본값이라 공개 함수로 지정할 수 없다).
