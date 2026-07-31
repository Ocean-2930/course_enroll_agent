"""장부 정합성 점검 API 통합 테스트."""

from fastapi.testclient import TestClient

from conftest import Ledger, moment


def _issue_and_complete(
    ledger: Ledger,
    academy_id: int,
    student_id: int,
    pass_type_id: int,
) -> dict:
    issued = ledger.issue(
        academy_id,
        student_id,
        pass_type_id,
        purchased_at=moment(-1),
        started_at=moment(-1),
    )
    record = ledger.reserve(
        academy_id,
        student_id,
        issued["id"],
        scheduled_at=moment(-1),
    )
    ledger.complete(academy_id, record["id"])
    return issued


def test_consistent_ledger_reports_no_mismatch(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=10)
    student = ledger.student(academy["id"], name="김민지")
    _issue_and_complete(ledger, academy["id"], student["id"], pass_type["id"])

    response = client.get(
        f"/api/academies/{academy['id']}/checks/ledger-consistency"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["academy_id"] == academy["id"]
    assert body["checked_count"] == 1
    assert body["mismatch_count"] == 0
    assert body["items"] == []


def test_restored_attendance_keeps_ledger_consistent(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=5)
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
    restored = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{record['id']}/restore"
        ),
        json={"reason": "완료 처리 실수"},
    )
    assert restored.status_code == 200

    body = client.get(
        f"/api/academies/{academy['id']}/checks/ledger-consistency"
    ).json()
    assert body["mismatch_count"] == 0


def test_mismatch_is_reported_without_being_fixed(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=10)
    student = ledger.student(academy["id"], name="김민지")
    issued = _issue_and_complete(
        ledger,
        academy["id"],
        student["id"],
        pass_type["id"],
    )
    pass_url = (
        f"/api/academies/{academy['id']}/students/"
        f"{student['id']}/passes/{issued['id']}"
    )
    assert client.get(pass_url).json()["remaining_sessions"] == 9

    # 정상 경로로는 만들 수 없는 어긋난 상태를 직접 만든다.
    ledger.corrupt_remaining_sessions(issued["id"], 4)

    check_url = f"/api/academies/{academy['id']}/checks/ledger-consistency"
    body = client.get(check_url).json()
    assert body["checked_count"] == 1
    assert body["mismatch_count"] == 1
    item = body["items"][0]
    assert item["student_pass_id"] == issued["id"]
    assert item["student_name"] == "김민지"
    assert item["pass_type_name"] == pass_type["name"]
    assert item["stored_remaining_sessions"] == 4
    assert item["expected_remaining_sessions"] == 9
    assert item["difference"] == -5

    # 조회 API는 값을 고치지 않는다. 다시 조회해도 결과가 같다.
    assert client.get(pass_url).json()["remaining_sessions"] == 4
    assert client.get(check_url).json() == body


def test_consistency_check_is_scoped_to_academy(
    client: TestClient,
    ledger: Ledger,
) -> None:
    first = ledger.academy("첫 번째 학원")
    second = ledger.academy("두 번째 학원")
    pass_type = ledger.pass_type(first["id"])
    student = ledger.student(first["id"])
    _issue_and_complete(ledger, first["id"], student["id"], pass_type["id"])

    other = client.get(
        f"/api/academies/{second['id']}/checks/ledger-consistency"
    ).json()
    assert other["checked_count"] == 0
    assert other["mismatch_count"] == 0

    missing = client.get("/api/academies/9999/checks/ledger-consistency")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACADEMY_NOT_FOUND"


def test_consistency_endpoint_exposes_stable_operation_id(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    path = "/api/academies/{academy_id}/checks/ledger-consistency"
    assert paths[path]["get"]["operationId"] == "check_ledger_consistency"
