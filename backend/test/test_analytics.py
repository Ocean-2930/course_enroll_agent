"""운영 분석(집계) API 통합 테스트."""

from fastapi.testclient import TestClient

from conftest import Ledger, day, moment


def test_dashboard_counts_period_and_management_targets(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=10)
    short_pass_type = ledger.pass_type(
        academy["id"],
        name="체험 2회권",
        total_sessions=2,
        validity_days=10,
    )
    active = ledger.student(academy["id"], name="활성 회원")
    inactive = ledger.student(academy["id"], name="비활성 회원")

    # 활성 회원: 오늘 발급 → 만료일이 미래이므로 활성으로 계산된다.
    issued = ledger.issue(
        academy["id"],
        active["id"],
        pass_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    # 10일 뒤 만료되는 잔여 2회 수강권(만료 예정 + 잔여 부족 대상).
    ledger.issue(
        academy["id"],
        active["id"],
        short_pass_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )

    past = ledger.reserve(
        academy["id"],
        active["id"],
        issued["id"],
        scheduled_at=moment(-2),
    )
    ledger.complete(academy["id"], past["id"])
    # 예정 시각이 지났는데 아직 RESERVED 인 예약(미처리).
    ledger.reserve(
        academy["id"],
        active["id"],
        issued["id"],
        scheduled_at=moment(-1),
    )
    cancelled = ledger.reserve(
        academy["id"],
        active["id"],
        issued["id"],
        scheduled_at=moment(-3),
    )
    ledger.cancel(academy["id"], cancelled["id"])

    response = client.get(
        f"/api/academies/{academy['id']}/analytics/dashboard",
        params={"date_from": day(-7), "date_to": day(0)},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["period"] == {"date_from": day(-7), "date_to": day(0)}
    assert body["students"]["total"] == 2
    assert body["students"]["active"] == 1
    assert body["students"]["inactive"] == 1
    assert body["students"]["new_in_period"] == 2
    assert body["student_passes"]["issued_in_period"] == 2
    assert body["student_passes"]["available"] == 2
    # 10회권에서 1회 사용 → 9회, 체험 2회권 2회 → 합계 11회
    assert body["student_passes"]["total_remaining_sessions"] == 11
    assert body["student_passes"]["expiring_within_14_days"] == 1
    assert body["student_passes"]["low_balance_count"] == 1
    assert body["attendance"]["completed_in_period"] == 1
    assert body["attendance"]["cancelled_in_period"] == 1
    assert body["attendance"]["reserved_in_period"] == 1
    assert body["attendance"]["pending_past"] == 1

    assert inactive["is_active"] is False


def test_dashboard_rejects_reversed_period_and_missing_academy(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()

    invalid = client.get(
        f"/api/academies/{academy['id']}/analytics/dashboard",
        params={"date_from": day(0), "date_to": day(-1)},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_DATE_RANGE"

    missing = client.get("/api/academies/9999/analytics/dashboard")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACADEMY_NOT_FOUND"


def test_registration_analytics_series_and_previous_period(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    first = ledger.student(academy["id"], name="회원1")
    second = ledger.student(academy["id"], name="회원2")
    ledger.issue(
        academy["id"],
        first["id"],
        pass_type["id"],
        purchased_at=moment(-1),
        started_at=moment(-1),
    )
    ledger.issue(
        academy["id"],
        second["id"],
        pass_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )

    response = client.get(
        f"/api/academies/{academy['id']}/analytics/registrations",
        params={"date_from": day(-2), "date_to": day(0), "group_by": "day"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["group_by"] == "day"
    assert body["total_students"] == 2
    assert body["total_student_passes"] == 2
    # 데이터가 없는 날도 0으로 채워 3일치가 모두 나온다.
    assert [point["period"] for point in body["series"]] == [
        day(-2),
        day(-1),
        day(0),
    ]
    assert {point["period"]: point["student_passes"] for point in body["series"]} == {
        day(-2): 0,
        day(-1): 1,
        day(0): 1,
    }
    # 수강생 등록일은 오늘(created_at)이므로 마지막 구간에 모두 잡힌다.
    assert body["series"][-1]["students"] == 2

    # 직전 기간에는 데이터가 없으므로 증감률은 0으로 나누지 않고 null.
    assert body["previous_period"]["date_from"] == day(-5)
    assert body["previous_period"]["date_to"] == day(-3)
    assert body["previous_period"]["total_students"] == 0
    assert body["student_change"] == {"count": 2, "rate": None}
    assert body["student_pass_change"] == {"count": 2, "rate": None}


def test_registration_analytics_change_rate_uses_previous_period(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    student = ledger.student(academy["id"])
    # 직전 기간(-3 ~ -2)에 2건, 선택 기간(-1 ~ 0)에 3건 발급한다.
    for offset in (-3, -2):
        ledger.issue(
            academy["id"],
            student["id"],
            pass_type["id"],
            purchased_at=moment(offset),
            started_at=moment(offset),
        )
    for offset in (-1, -1, 0):
        ledger.issue(
            academy["id"],
            student["id"],
            pass_type["id"],
            purchased_at=moment(offset),
            started_at=moment(offset),
        )

    response = client.get(
        f"/api/academies/{academy['id']}/analytics/registrations",
        params={"date_from": day(-1), "date_to": day(0)},
    )
    body = response.json()
    assert body["total_student_passes"] == 3
    assert body["previous_period"]["total_student_passes"] == 2
    assert body["student_pass_change"] == {"count": 1, "rate": 50.0}


def test_attendance_analytics_totals_and_breakdowns(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    group = ledger.pass_type(academy["id"], name="그룹 10회권")
    personal = ledger.pass_type(academy["id"], name="개인 5회권", total_sessions=5)
    student = ledger.student(academy["id"])
    group_pass = ledger.issue(
        academy["id"],
        student["id"],
        group["id"],
        purchased_at=moment(-3),
        started_at=moment(-3),
    )
    personal_pass = ledger.issue(
        academy["id"],
        student["id"],
        personal["id"],
        purchased_at=moment(-3),
        started_at=moment(-3),
    )

    for offset in (-2, -1):
        record = ledger.reserve(
            academy["id"],
            student["id"],
            group_pass["id"],
            class_name="그룹 필라테스",
            scheduled_at=moment(offset),
        )
        ledger.complete(academy["id"], record["id"])
    personal_record = ledger.reserve(
        academy["id"],
        student["id"],
        personal_pass["id"],
        class_name="개인 레슨",
        scheduled_at=moment(-1),
    )
    ledger.complete(academy["id"], personal_record["id"])
    cancelled = ledger.reserve(
        academy["id"],
        student["id"],
        group_pass["id"],
        scheduled_at=moment(-1),
    )
    ledger.cancel(academy["id"], cancelled["id"])
    # 예정 시각이 지난 미처리 예약.
    ledger.reserve(
        academy["id"],
        student["id"],
        group_pass["id"],
        scheduled_at=moment(-1),
    )

    response = client.get(
        f"/api/academies/{academy['id']}/analytics/attendance",
        params={"date_from": day(-3), "date_to": day(0)},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["totals"] == {
        "reserved": 1,
        "completed": 3,
        "cancelled": 1,
        "pending_past": 1,
    }
    assert body["by_class_name"] == [
        {"class_name": "그룹 필라테스", "completed": 2},
        {"class_name": "개인 레슨", "completed": 1},
    ]
    assert body["by_pass_type"] == [
        {
            "pass_type_id_snapshot": group["id"],
            "pass_type_name_snapshot": "그룹 10회권",
            "completed": 2,
        },
        {
            "pass_type_id_snapshot": personal["id"],
            "pass_type_name_snapshot": "개인 5회권",
            "completed": 1,
        },
    ]
    series = {point["period"]: point for point in body["series"]}
    assert series[day(-2)]["completed"] == 1
    assert series[day(-1)]["completed"] == 2
    assert series[day(-1)]["cancelled"] == 1
    assert series[day(0)]["completed"] == 0


def test_pass_type_analytics_uses_snapshot_after_deletion(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(
        academy["id"],
        name="그룹 필라테스 10회권",
        total_sessions=10,
        price=300000,
    )
    student = ledger.student(academy["id"])
    issued = ledger.issue(
        academy["id"],
        student["id"],
        pass_type["id"],
        purchased_at=moment(-1),
        started_at=moment(-1),
    )
    record = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(-1),
    )
    ledger.complete(academy["id"], record["id"])

    deleted = client.delete(
        f"/api/academies/{academy['id']}/pass-types/{pass_type['id']}"
    )
    assert deleted.status_code == 204

    response = client.get(
        f"/api/academies/{academy['id']}/analytics/pass-types",
        params={"date_from": day(-7), "date_to": day(0)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    item = body["items"][0]
    assert item["pass_type_id_snapshot"] == pass_type["id"]
    assert item["pass_type_name_snapshot"] == "그룹 필라테스 10회권"
    assert item["issued_count"] == 1
    assert item["issued_sessions"] == 10
    assert item["remaining_sessions"] == 9
    assert item["used_sessions"] == 1
    assert item["completed_attendance_count"] == 1
    assert item["issued_price_total"] == 300000


def test_analytics_never_mixes_other_academies(
    client: TestClient,
    ledger: Ledger,
) -> None:
    first = ledger.academy("첫 번째 학원")
    second = ledger.academy("두 번째 학원")
    first_type = ledger.pass_type(first["id"])
    second_type = ledger.pass_type(second["id"])
    first_student = ledger.student(first["id"], name="A 회원")
    second_student = ledger.student(second["id"], name="B 회원")
    first_pass = ledger.issue(
        first["id"],
        first_student["id"],
        first_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    ledger.issue(
        second["id"],
        second_student["id"],
        second_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    record = ledger.reserve(
        first["id"],
        first_student["id"],
        first_pass["id"],
        scheduled_at=moment(0),
    )
    ledger.complete(first["id"], record["id"])

    dashboard = client.get(
        f"/api/academies/{second['id']}/analytics/dashboard"
    ).json()
    assert dashboard["students"]["total"] == 1
    assert dashboard["student_passes"]["issued_in_period"] == 1
    assert dashboard["attendance"]["completed_in_period"] == 0

    pass_types = client.get(
        f"/api/academies/{second['id']}/analytics/pass-types"
    ).json()
    assert [item["pass_type_id_snapshot"] for item in pass_types["items"]] == [
        second_type["id"]
    ]


def test_analytics_endpoints_expose_stable_operation_ids(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert (
        paths["/api/academies/{academy_id}/analytics/dashboard"]["get"][
            "operationId"
        ]
        == "get_academy_dashboard"
    )
    assert (
        paths["/api/academies/{academy_id}/analytics/registrations"]["get"][
            "operationId"
        ]
        == "get_registration_analytics"
    )
    assert (
        paths["/api/academies/{academy_id}/analytics/attendance"]["get"][
            "operationId"
        ]
        == "get_attendance_analytics"
    )
    assert (
        paths["/api/academies/{academy_id}/analytics/pass-types"]["get"][
            "operationId"
        ]
        == "get_pass_type_analytics"
    )
