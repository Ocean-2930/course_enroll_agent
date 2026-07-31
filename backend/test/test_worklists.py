"""운영 관리 대상(할 일) 목록 API 통합 테스트."""

from fastapi.testclient import TestClient

from conftest import Ledger, day, moment


def _issue_expiring_in(
    ledger: Ledger,
    academy_id: int,
    student_id: int,
    *,
    name: str,
    days_left: int,
    total_sessions: int = 10,
) -> dict:
    """만료일이 오늘 + days_left 인 수강권을 발급한다."""
    validity_days = 30
    pass_type = ledger.pass_type(
        academy_id,
        name=name,
        total_sessions=total_sessions,
        validity_days=validity_days,
    )
    started = moment(days_left - validity_days)
    return ledger.issue(
        academy_id,
        student_id,
        pass_type["id"],
        purchased_at=started,
        started_at=started,
    )


def test_pending_attendance_lists_only_past_reservations(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    student = ledger.student(academy["id"], name="김민지")
    issued = ledger.issue(
        academy["id"],
        student["id"],
        pass_type["id"],
        purchased_at=moment(-1),
        started_at=moment(-1),
    )
    past = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        class_name="그룹 필라테스",
        scheduled_at=moment(-1),
    )
    # 미래 예약과 이미 완료된 과거 예약은 미처리 목록에 포함되지 않는다.
    ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(3),
    )
    completed = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(-2),
    )
    ledger.complete(academy["id"], completed["id"])

    response = client.get(
        f"/api/academies/{academy['id']}/worklists/pending-attendance"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    item = body["items"][0]
    assert item["attendance_record_id"] == past["id"]
    assert item["student_name"] == "김민지"
    assert item["class_name"] == "그룹 필라테스"
    assert item["status"] == "RESERVED"
    assert item["remaining_sessions"] == 9
    assert item["expire_date"] is not None


def test_expiring_passes_within_14_days(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    student = ledger.student(academy["id"], name="김민지")
    soon = _issue_expiring_in(
        ledger,
        academy["id"],
        student["id"],
        name="곧 만료 10회권",
        days_left=7,
    )
    _issue_expiring_in(
        ledger,
        academy["id"],
        student["id"],
        name="여유 10회권",
        days_left=25,
    )

    response = client.get(
        f"/api/academies/{academy['id']}/worklists/expiring-passes",
        params={"days": 14},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    item = body["items"][0]
    assert item["student_pass_id"] == soon["id"]
    assert item["pass_type_name"] == "곧 만료 10회권"
    assert item["expire_date"] == day(7)
    assert item["days_left"] == 7
    assert item["last_completed_at"] is None

    wider = client.get(
        f"/api/academies/{academy['id']}/worklists/expiring-passes",
        params={"days": 30},
    ).json()
    assert wider["pagination"]["total"] == 2


def test_expired_passes_with_remaining_sessions(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    student = ledger.student(academy["id"], name="김민지")
    expired = _issue_expiring_in(
        ledger,
        academy["id"],
        student["id"],
        name="만료된 10회권",
        days_left=-3,
    )
    _issue_expiring_in(
        ledger,
        academy["id"],
        student["id"],
        name="유효한 10회권",
        days_left=10,
    )

    response = client.get(
        f"/api/academies/{academy['id']}/worklists/expiring-passes",
        params={"expired_only": True, "remaining_only": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pagination"]["total"] == 1
    item = body["items"][0]
    assert item["student_pass_id"] == expired["id"]
    assert item["remaining_sessions"] == 10
    assert item["days_left"] == -3

    # 기본 조회(만료 제외)에는 만료된 수강권이 나오지 않는다.
    default = client.get(
        f"/api/academies/{academy['id']}/worklists/expiring-passes",
        params={"days": 30},
    ).json()
    assert [item["student_pass_id"] for item in default["items"]] == [
        item["student_pass_id"]
        for item in default["items"]
        if item["days_left"] >= 0
    ]


def test_low_balance_passes_include_zero_remaining(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    student = ledger.student(academy["id"], name="김민지")
    two_sessions = ledger.pass_type(
        academy["id"],
        name="체험 2회권",
        total_sessions=2,
    )
    ten_sessions = ledger.pass_type(academy["id"], name="10회권")
    small = ledger.issue(
        academy["id"],
        student["id"],
        two_sessions["id"],
        purchased_at=moment(-1),
        started_at=moment(-1),
    )
    ledger.issue(
        academy["id"],
        student["id"],
        ten_sessions["id"],
        purchased_at=moment(-1),
        started_at=moment(-1),
    )

    response = client.get(
        f"/api/academies/{academy['id']}/worklists/low-balance-passes",
        params={"max_remaining": 3},
    )
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["student_pass_id"] == small["id"]
    assert body["items"][0]["remaining_sessions"] == 2

    # 2회를 모두 사용하면 잔여 0회가 되고 여전히 목록에 남는다.
    for offset in (-1, 0):
        record = ledger.reserve(
            academy["id"],
            student["id"],
            small["id"],
            scheduled_at=moment(offset),
        )
        ledger.complete(academy["id"], record["id"])

    exhausted = client.get(
        f"/api/academies/{academy['id']}/worklists/low-balance-passes",
        params={"max_remaining": 0},
    ).json()
    assert exhausted["pagination"]["total"] == 1
    assert exhausted["items"][0]["remaining_sessions"] == 0
    assert exhausted["items"][0]["last_completed_at"] is not None


def test_reregistration_candidates_deduplicate_with_reasons(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()

    # 1) 잔여가 적고 곧 만료 → 두 사유가 함께 잡힌다.
    both = ledger.student(academy["id"], name="사유 두 개")
    both_type = ledger.pass_type(
        academy["id"],
        name="곧 만료 2회권",
        total_sessions=2,
        validity_days=30,
    )
    ledger.issue(
        academy["id"],
        both["id"],
        both_type["id"],
        purchased_at=moment(-25),
        started_at=moment(-25),
    )

    # 2) 모든 수강권을 소진 → ALL_PASSES_EXHAUSTED
    exhausted = ledger.student(academy["id"], name="소진 회원")
    single_type = ledger.pass_type(
        academy["id"],
        name="1회권",
        total_sessions=1,
        validity_days=60,
    )
    exhausted_pass = ledger.issue(
        academy["id"],
        exhausted["id"],
        single_type["id"],
        purchased_at=moment(-1),
        started_at=moment(-1),
    )
    used = ledger.reserve(
        academy["id"],
        exhausted["id"],
        exhausted_pass["id"],
        scheduled_at=moment(-1),
    )
    ledger.complete(academy["id"], used["id"])

    # 3) 만료됐지만 최근 완료 수강 이력이 있음
    lapsed = ledger.student(academy["id"], name="만료 회원")
    lapsed_type = ledger.pass_type(
        academy["id"],
        name="만료 10회권",
        total_sessions=10,
        validity_days=30,
    )
    lapsed_pass = ledger.issue(
        academy["id"],
        lapsed["id"],
        lapsed_type["id"],
        purchased_at=moment(-33),
        started_at=moment(-33),
    )
    recent = ledger.reserve(
        academy["id"],
        lapsed["id"],
        lapsed_pass["id"],
        scheduled_at=moment(-5),
    )
    ledger.complete(academy["id"], recent["id"])

    # 4) 여유 있는 회원은 후보가 아니다.
    healthy = ledger.student(academy["id"], name="여유 회원")
    healthy_type = ledger.pass_type(
        academy["id"],
        name="여유 20회권",
        total_sessions=20,
        validity_days=180,
    )
    ledger.issue(
        academy["id"],
        healthy["id"],
        healthy_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )

    response = client.get(
        f"/api/academies/{academy['id']}/worklists/reregistration-candidates"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["criteria"] == {
        "max_remaining": 3,
        "expiring_within_days": 14,
        "recent_attendance_days": 30,
    }

    by_name = {item["student_name"]: item for item in body["items"]}
    assert set(by_name) == {"사유 두 개", "소진 회원", "만료 회원"}
    assert body["pagination"]["total"] == 3
    # 한 수강생은 한 번만 나오고 사유는 배열로 모인다.
    assert len(body["items"]) == 3

    assert by_name["사유 두 개"]["reasons"] == [
        "LOW_REMAINING_SESSIONS",
        "EXPIRING_SOON",
    ]
    assert by_name["사유 두 개"]["remaining_sessions"] == 2
    assert by_name["사유 두 개"]["nearest_expire_date"] == day(5)

    assert by_name["소진 회원"]["reasons"] == ["ALL_PASSES_EXHAUSTED"]
    assert by_name["소진 회원"]["remaining_sessions"] == 0

    assert by_name["만료 회원"]["reasons"] == [
        "EXPIRED_WITH_RECENT_ATTENDANCE"
    ]
    assert by_name["만료 회원"]["last_completed_at"] is not None


def test_worklists_are_scoped_to_academy(
    client: TestClient,
    ledger: Ledger,
) -> None:
    first = ledger.academy("첫 번째 학원")
    second = ledger.academy("두 번째 학원")
    student = ledger.student(first["id"], name="A 회원")
    _issue_expiring_in(
        ledger,
        first["id"],
        student["id"],
        name="곧 만료 10회권",
        days_left=3,
    )

    other = client.get(
        f"/api/academies/{second['id']}/worklists/expiring-passes"
    ).json()
    assert other["items"] == []
    assert other["pagination"]["total"] == 0

    missing = client.get("/api/academies/9999/worklists/expiring-passes")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACADEMY_NOT_FOUND"


def test_worklist_endpoints_expose_stable_operation_ids(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/academies/{academy_id}/worklists/pending-attendance": (
            "list_pending_attendance"
        ),
        "/api/academies/{academy_id}/worklists/expiring-passes": (
            "list_expiring_passes"
        ),
        "/api/academies/{academy_id}/worklists/low-balance-passes": (
            "list_low_balance_passes"
        ),
        "/api/academies/{academy_id}/worklists/reregistration-candidates": (
            "list_reregistration_candidates"
        ),
    }
    for path, operation_id in expected.items():
        assert paths[path]["get"]["operationId"] == operation_id
