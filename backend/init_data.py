"""테스트용 샘플 데이터가 채워진 SQLite 데이터베이스를 새로 만든다.

`init_db.py`와 똑같이 기존 DB 파일을 삭제하고 최신 전체 스키마를 만든 뒤,
사업소 2곳 분량의 수강권 종류·수강생·발급·수강 기록을 채워 넣는다.

주의: 실행하면 기존 데이터가 모두 사라진다.

업무 데이터는 전부 `database.db_connector`의 공개 함수로 만든다. 그래서
스냅샷 컬럼, 잔여 횟수 차감, 만료일 계산 같은 규칙이 실제 운영과 동일하게
적용된다. 예외는 수강생 등록일(`created_at`)을 과거로 되돌리는 부분 하나이며,
DB 기본값(CURRENT_TIMESTAMP)은 공개 함수로 바꿀 수 없고 신규 등록 통계를
확인하려면 과거 등록일이 필요하기 때문이다. 이 처리는 초기화 전용이다.

사용법:

    python init_data.py                 # backend/local_database.db 를 다시 만든다
    python init_data.py 경로.db          # 다른 경로에 만든다(로컬 DB 보존)
"""

from datetime import date, datetime, timedelta
from pathlib import Path
import random
import sys
from typing import Any

from database import db_connector
from database.connection import DATABASE_PATH, connect_database
from init_db import init_db


# 실행할 때마다 같은 데이터를 만들기 위한 고정 시드.
RANDOM_SEED = 20260731

# 수업이 열리는 시간대.
CLASS_HOURS = (7, 9, 10, 11, 14, 16, 18, 19, 20)

# 로컬 시각을 SQLite 의 UTC 기본값 형식으로 바꿀 때 쓰는 시간대 차이.
LOCAL_UTC_OFFSET = datetime.now().astimezone().utcoffset() or timedelta(0)

SURNAMES = (
    "김", "이", "박", "최", "정", "강", "조", "윤", "장", "임",
    "한", "오", "서", "신", "권", "황", "안", "송", "류", "홍",
)
GIVEN_NAMES = (
    "민지", "서준", "도윤", "지우", "하은", "예준", "수아", "지호", "다은", "시우",
    "은우", "채원", "지민", "유진", "하준", "서연", "지안", "예은", "시윤", "나윤",
    "준서", "소율", "태은", "가온", "라온", "해린", "지환", "여울", "새봄", "이든",
    "루아", "한별", "도경", "세아", "연우",
)

# 아카데미별 수강권 종류. role 은 아래 코호트 정의에서 참조한다.
ACADEMIES = (
    {
        "name": "한빛 필라테스",
        "phone": "02-555-0101",
        "address": "서울특별시 마포구 연남로 12",
        "phone_prefix": "010-2401",
        "class_names": (
            "그룹 필라테스",
            "리포머 소그룹",
            "개인 레슨",
            "주말 필라테스",
        ),
        "pass_types": (
            {
                "role": "trial",
                "name": "체험 2회권",
                "total_sessions": 2,
                "validity_days": 14,
                "price": 40000,
                "description": "처음 오신 분을 위한 체험 수업 2회.",
            },
            {
                "role": "standard",
                "name": "그룹 필라테스 10회권",
                "total_sessions": 10,
                "validity_days": 90,
                "price": 350000,
                "description": "가장 많이 선택하는 기본 그룹 수업권.",
            },
            {
                "role": "premium",
                "name": "그룹 필라테스 20회권",
                "total_sessions": 20,
                "validity_days": 180,
                "price": 640000,
                "description": "장기 등록 회원을 위한 20회권.",
            },
            {
                "role": "private",
                "name": "개인 레슨 5회권",
                "total_sessions": 5,
                "validity_days": 60,
                "price": 500000,
                "description": "1:1 자세 교정 중심 개인 레슨.",
            },
        ),
    },
    {
        "name": "그린 요가원",
        "phone": "031-777-2020",
        "address": "경기도 성남시 분당구 정자일로 30",
        "phone_prefix": "010-7702",
        "class_names": (
            "하타 요가",
            "빈야사 요가",
            "개인 요가",
            "새벽 요가",
        ),
        "pass_types": (
            {
                "role": "trial",
                "name": "요가 체험 3회권",
                "total_sessions": 3,
                "validity_days": 21,
                "price": 45000,
                "description": "요가가 처음인 분을 위한 체험권.",
            },
            {
                "role": "standard",
                "name": "데일리 요가 10회권",
                "total_sessions": 10,
                "validity_days": 90,
                "price": 300000,
                "description": "주 3회 수련에 맞춘 기본권.",
            },
            {
                "role": "premium",
                "name": "데일리 요가 20회권",
                "total_sessions": 20,
                "validity_days": 180,
                "price": 540000,
                "description": "꾸준히 수련하는 회원을 위한 장기권.",
            },
            {
                "role": "private",
                "name": "개인 요가 5회권",
                "total_sessions": 5,
                "validity_days": 45,
                "price": 450000,
                "description": "체형에 맞춘 1:1 요가 수업.",
            },
        ),
    },
)

# 수강생 코호트. 화면의 모든 목록·지표에 데이터가 잡히도록 구성했다.
#
# 수강권 spec 키
#   role      : 발급할 수강권 종류
#   start     : 시작일 오프셋(오늘 기준, 일)
#   expire_in : 만료일 오프셋 범위. 지정하면 start 대신 만료일에서 역산한다.
#   leave     : 완료 처리 후 남길 잔여 횟수
#   cancelled : 취소 처리할 예약 수
#   pending   : 예정 시각이 지났는데 그대로 두는 예약 수(미처리)
#   today     : 오늘 예약 수
#   future    : 미래 예약 수
COHORTS = (
    {
        "key": "신규 활성 회원",
        "count": 5,
        "created": (-20, -3),
        "passes": (
            {"role": "standard", "start": -7, "leave": 8, "today": 1, "future": 1},
        ),
    },
    {
        "key": "곧 만료 예정",
        "count": 5,
        "created": (-120, -80),
        "passes": (
            {
                "role": "standard",
                "expire_in": (3, 14),
                "leave": 5,
                "cancelled": 1,
                "pending": 1,
                "future": 1,
            },
        ),
    },
    {
        "key": "잔여 횟수 부족",
        "count": 4,
        "created": (-150, -100),
        "passes": (
            {"role": "standard", "start": -60, "leave": 2, "cancelled": 1},
        ),
    },
    {
        "key": "만료됐지만 잔여 있음",
        "count": 3,
        "created": (-200, -150),
        "passes": (
            {"role": "standard", "expire_in": (-30, -6), "leave": 4},
        ),
    },
    {
        "key": "만료 + 최근 수강 이력",
        "count": 3,
        "created": (-170, -120),
        "passes": (
            {"role": "standard", "expire_in": (-10, -3), "leave": 2},
        ),
    },
    {
        "key": "장기 회원",
        "count": 4,
        "created": (-300, -200),
        "passes": (
            {"role": "standard", "start": -200, "leave": 2},
            {
                "role": "premium",
                "start": -40,
                "leave": 14,
                "today": 1,
                "future": 1,
            },
        ),
    },
    {
        "key": "체험 후 소진",
        "count": 2,
        "created": (-15, -5),
        "passes": (
            {"role": "trial", "start": -10, "leave": 0},
        ),
    },
    {
        "key": "일반 활성 회원",
        "count": 3,
        "created": (-90, -40),
        "passes": (
            {"role": "standard", "start": -45, "leave": 5, "future": 1},
        ),
    },
    {
        "key": "개인 레슨 회원",
        "count": 2,
        "created": (-60, -20),
        "passes": (
            {"role": "private", "start": -20, "leave": 2, "future": 1},
        ),
    },
    {
        "key": "체험 후 미등록",
        "count": 2,
        "created": (-12, -2),
        "passes": (),
    },
    {
        "key": "미처리 예약 보유",
        "count": 2,
        "created": (-100, -60),
        "passes": (
            {
                "role": "standard",
                "start": -40,
                "leave": 6,
                "pending": 3,
                "today": 1,
            },
        ),
    },
)


def _local_iso(day: date, hour: int = 10, minute: int = 0) -> str:
    return datetime(day.year, day.month, day.day, hour, minute).isoformat()


def _utc_text(day: date, hour: int, minute: int) -> str:
    """로컬 시각을 SQLite CURRENT_TIMESTAMP 와 같은 UTC 문자열로 바꾼다."""
    local = datetime(day.year, day.month, day.day, hour, minute)
    return (local - LOCAL_UTC_OFFSET).strftime("%Y-%m-%d %H:%M:%S")


def _random_class_datetime(
    rng: random.Random,
    start: date,
    end: date,
) -> str:
    """[start, end] 사이의 수업 시간 하나를 고른다."""
    if end < start:
        end = start
    picked = start + timedelta(days=rng.randint(0, (end - start).days))
    return _local_iso(
        picked,
        rng.choice(CLASS_HOURS),
        rng.choice((0, 30)),
    )


def _backdate_students(
    database_path: Path,
    backdates: list[tuple[str, int]],
) -> None:
    """초기화 전용: 수강생 등록일을 과거로 되돌린다.

    `created_at` 은 DB 기본값(CURRENT_TIMESTAMP)이라 공개 함수로 지정할 수
    없다. 신규 등록 통계를 확인하려면 과거 등록일이 필요하므로 여기서만
    직접 수정한다.
    """
    connection = connect_database(database_path)
    try:
        with connection:
            connection.executemany(
                """
                UPDATE students
                SET created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                [(text, text, student_id) for text, student_id in backdates],
            )
    finally:
        connection.close()


def _seed_student_pass(
    rng: random.Random,
    academy: dict[str, Any],
    student_id: int,
    pass_type: dict[str, Any],
    spec: dict[str, Any],
    today: date,
    counters: dict[str, int],
) -> None:
    """수강권 한 장을 발급하고 그 위에 수강 기록을 만든다."""
    validity_days = pass_type["validity_days"]
    if "expire_in" in spec:
        low, high = spec["expire_in"]
        start_offset = rng.randint(low, high) - validity_days
    else:
        start_offset = spec["start"]
    start_day = today + timedelta(days=start_offset)
    started_at = _local_iso(start_day, 10)

    issued = db_connector.issue_student_pass(
        academy["id"],
        student_id,
        {
            "pass_type_id": pass_type["id"],
            "purchased_at": started_at,
            "started_at": started_at,
        },
    )
    counters["student_passes"] += 1

    expire_day = date.fromisoformat(issued["expire_date"])
    total_sessions = issued["total_sessions"]
    student_pass_id = issued["id"]
    class_names = academy["class_names"]

    reservations = (
        spec.get("cancelled", 0)
        + spec.get("pending", 0)
        + spec.get("today", 0)
        + spec.get("future", 0)
    )
    # 예약을 만들려면 그 시점에 잔여 횟수가 남아 있어야 한다.
    leave = max(spec.get("leave", 0), 1 if reservations else 0)
    completed_count = max(total_sessions - leave, 0)
    remaining = total_sessions

    used_end = min(today, expire_day)
    for _ in range(completed_count):
        if remaining <= 0:
            break
        scheduled_at = _random_class_datetime(rng, start_day, used_end)
        record = db_connector.create_attendance_record(
            academy["id"],
            {
                "student_id": student_id,
                "student_pass_id": student_pass_id,
                "class_name": rng.choice(class_names),
                "scheduled_at": scheduled_at,
                "memo": None,
            },
        )
        completed_at = (
            datetime.fromisoformat(scheduled_at) + timedelta(hours=1)
        ).isoformat()
        db_connector.complete_attendance(
            academy["id"],
            record["id"],
            completed_at,
        )
        remaining -= 1
        counters["attendance_records"] += 1
        counters["completed"] += 1

    for _ in range(spec.get("cancelled", 0)):
        if remaining <= 0:
            break
        scheduled_at = _random_class_datetime(rng, start_day, used_end)
        record = db_connector.create_attendance_record(
            academy["id"],
            {
                "student_id": student_id,
                "student_pass_id": student_pass_id,
                "class_name": rng.choice(class_names),
                "scheduled_at": scheduled_at,
                "memo": None,
            },
        )
        db_connector.cancel_attendance(
            academy["id"],
            record["id"],
            cancelled_at=scheduled_at,
            memo="회원 요청으로 취소",
        )
        counters["attendance_records"] += 1
        counters["cancelled"] += 1

    # 예정 시각이 지났는데 처리하지 않은 예약(미처리 목록에 잡힌다).
    pending_end = min(today - timedelta(days=1), expire_day)
    for _ in range(spec.get("pending", 0)):
        if remaining <= 0 or pending_end < start_day:
            break
        db_connector.create_attendance_record(
            academy["id"],
            {
                "student_id": student_id,
                "student_pass_id": student_pass_id,
                "class_name": rng.choice(class_names),
                "scheduled_at": _random_class_datetime(
                    rng,
                    start_day,
                    pending_end,
                ),
                "memo": None,
            },
        )
        counters["attendance_records"] += 1
        counters["pending_past"] += 1

    if expire_day >= today:
        for _ in range(spec.get("today", 0)):
            if remaining <= 0:
                break
            db_connector.create_attendance_record(
                academy["id"],
                {
                    "student_id": student_id,
                    "student_pass_id": student_pass_id,
                    "class_name": rng.choice(class_names),
                    "scheduled_at": _local_iso(
                        today,
                        rng.choice(CLASS_HOURS),
                        rng.choice((0, 30)),
                    ),
                    "memo": None,
                },
            )
            counters["attendance_records"] += 1
            counters["reserved_today"] += 1

    future_end = min(today + timedelta(days=14), expire_day)
    if future_end > today:
        for _ in range(spec.get("future", 0)):
            if remaining <= 0:
                break
            db_connector.create_attendance_record(
                academy["id"],
                {
                    "student_id": student_id,
                    "student_pass_id": student_pass_id,
                    "class_name": rng.choice(class_names),
                    "scheduled_at": _random_class_datetime(
                        rng,
                        today + timedelta(days=1),
                        future_end,
                    ),
                    "memo": None,
                },
            )
            counters["attendance_records"] += 1
            counters["reserved_future"] += 1


def _seed_academy(
    rng: random.Random,
    academy_spec: dict[str, Any],
    academy_index: int,
    today: date,
    counters: dict[str, int],
    backdates: list[tuple[str, int]],
) -> None:
    academy = db_connector.create_academy(
        {
            "name": academy_spec["name"],
            "phone": academy_spec["phone"],
            "address": academy_spec["address"],
        }
    )
    counters["academies"] += 1

    pass_types: dict[str, dict[str, Any]] = {}
    for template in academy_spec["pass_types"]:
        created = db_connector.create_pass_type(
            academy["id"],
            {
                "name": template["name"],
                "description": template["description"],
                "total_sessions": template["total_sessions"],
                "validity_days": template["validity_days"],
                "price": template["price"],
            },
        )
        pass_types[template["role"]] = created
        counters["pass_types"] += 1

    context = {
        "id": academy["id"],
        "class_names": academy_spec["class_names"],
    }

    student_number = 0
    for cohort in COHORTS:
        for _ in range(cohort["count"]):
            student_number += 1
            name = rng.choice(SURNAMES) + rng.choice(GIVEN_NAMES)
            phone = "{}-{:04d}".format(
                academy_spec["phone_prefix"],
                1000 + student_number,
            )
            email = (
                "member{:02d}{}@example.com".format(
                    student_number,
                    academy_index + 1,
                )
                if student_number % 3 != 0
                else None
            )
            student = db_connector.create_student(
                context["id"],
                {
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "memo": cohort["key"],
                },
            )
            counters["students"] += 1

            low, high = cohort["created"]
            created_day = today + timedelta(days=rng.randint(low, high))
            backdates.append(
                (
                    _utc_text(
                        created_day,
                        rng.choice((10, 13, 16, 19)),
                        rng.choice((0, 30)),
                    ),
                    student["id"],
                )
            )

            for spec in cohort["passes"]:
                _seed_student_pass(
                    rng,
                    context,
                    student["id"],
                    pass_types[spec["role"]],
                    spec,
                    today,
                    counters,
                )


def seed_database(database_path: Path = DATABASE_PATH) -> dict[str, int]:
    """DB를 새로 만들고 테스트용 데이터를 채운다."""
    init_db(database_path)
    db_connector.DATABASE_PATH = database_path

    rng = random.Random(RANDOM_SEED)
    today = date.today()
    counters = {
        "academies": 0,
        "pass_types": 0,
        "students": 0,
        "student_passes": 0,
        "attendance_records": 0,
        "completed": 0,
        "cancelled": 0,
        "pending_past": 0,
        "reserved_today": 0,
        "reserved_future": 0,
    }
    backdates: list[tuple[str, int]] = []

    for index, academy_spec in enumerate(ACADEMIES):
        _seed_academy(rng, academy_spec, index, today, counters, backdates)

    _backdate_students(database_path, backdates)
    return counters


def main() -> int:
    database_path = (
        Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DATABASE_PATH
    )
    print(f"기존 데이터를 삭제하고 새로 만듭니다: {database_path}")
    counters = seed_database(database_path)
    print("샘플 데이터를 채웠습니다.")
    labels = (
        ("academies", "아카데미"),
        ("pass_types", "수강권 종류"),
        ("students", "수강생"),
        ("student_passes", "발급된 수강권"),
        ("attendance_records", "수강 기록"),
        ("completed", "  └ 완료"),
        ("cancelled", "  └ 취소"),
        ("pending_past", "  └ 미처리(과거 예약)"),
        ("reserved_today", "  └ 오늘 예약"),
        ("reserved_future", "  └ 향후 예약"),
    )
    for key, label in labels:
        print(f"  {label}: {counters[key]}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
