"""회원 포털 API(구매·삭제·예약·체크인·퇴실·홈 요약) 통합 테스트."""

from fastapi.testclient import TestClient

from conftest import Ledger, day, moment


def _pass_url(academy_id: int, student_id: int, student_pass_id: int) -> str:
    return (
        f"/api/academies/{academy_id}/students/{student_id}"
        f"/passes/{student_pass_id}"
    )


def test_purchase_copies_snapshots_and_updates_expire_date(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    other = ledger.academy("다른 학원")
    pass_type = ledger.pass_type(
        academy["id"],
        name="개인 레슨 10회권",
        total_sessions=10,
        validity_days=90,
        price=500000,
        session_duration_minutes=50,
    )
    other_type = ledger.pass_type(other["id"], name="다른 학원 10회권")
    student = ledger.student(academy["id"], name="김민지")
    assert student["expire_date"] is None

    issued = ledger.issue(
        academy["id"],
        student["id"],
        pass_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    assert issued["pass_type_name_snapshot"] == "개인 레슨 10회권"
    assert issued["session_duration_minutes_snapshot"] == 50
    assert issued["remaining_sessions"] == 10
    assert issued["used_sessions"] == 0
    assert issued["expire_date"] == day(90)
    assert issued["student_expire_date"] == day(90)

    student_url = f"/api/academies/{academy['id']}/students/{student['id']}"
    assert client.get(student_url).json()["expire_date"] == day(90)

    # 다른 아카데미 상품은 구매할 수 없다.
    rejected = client.post(
        f"/api/academies/{academy['id']}/students/{student['id']}/passes",
        json={"pass_type_id": other_type["id"]},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "PASS_TYPE_ACADEMY_MISMATCH"

    # 실패한 구매는 아무것도 남기지 않는다.
    passes = client.get(
        f"/api/academies/{academy['id']}/students/{student['id']}/passes"
    ).json()
    assert passes["pagination"]["total"] == 1


def test_pass_snapshot_survives_pass_type_change(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], session_duration_minutes=50)
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])

    updated = client.patch(
        f"/api/academies/{academy['id']}/pass-types/{pass_type['id']}",
        json={"session_duration_minutes": 90},
    )
    assert updated.status_code == 200
    assert updated.json()["session_duration_minutes"] == 90

    stored = client.get(
        _pass_url(academy["id"], student["id"], issued["id"])
    ).json()
    assert stored["session_duration_minutes_snapshot"] == 50


def test_delete_pass_with_remaining_sessions_recalculates_expire_date(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    short = ledger.pass_type(academy["id"], name="30일권", validity_days=30)
    long = ledger.pass_type(academy["id"], name="180일권", validity_days=180)
    student = ledger.student(academy["id"])
    short_pass = ledger.issue(
        academy["id"],
        student["id"],
        short["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    long_pass = ledger.issue(
        academy["id"],
        student["id"],
        long["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    student_url = f"/api/academies/{academy['id']}/students/{student['id']}"
    assert client.get(student_url).json()["expire_date"] == day(180)
    assert long_pass["remaining_sessions"] == 10

    # 잔여 횟수가 남아 있어도 삭제된다.
    deleted = client.delete(
        _pass_url(academy["id"], student["id"], long_pass["id"])
    )
    assert deleted.status_code == 204
    # 남은 수강권 기준으로 만료일이 다시 계산된다.
    assert client.get(student_url).json()["expire_date"] == day(30)

    assert client.delete(
        _pass_url(academy["id"], student["id"], short_pass["id"])
    ).status_code == 204
    assert client.get(student_url).json()["expire_date"] is None
    assert client.get(
        f"/api/academies/{academy['id']}/students/{student['id']}/passes"
    ).json()["pagination"]["total"] == 0


def test_reservation_calculates_end_time_and_keeps_sessions(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], session_duration_minutes=50)
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])

    reservation = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=day(1) + "T19:00:00",
    )
    assert reservation["scheduled_at"] == day(1) + "T19:00:00"
    assert reservation["scheduled_end_at"] == day(1) + "T19:50:00"
    assert reservation["status"] == "RESERVED"
    assert reservation["session_delta"] == 0
    assert reservation["checked_in_at"] is None
    assert reservation["checked_out_at"] is None

    # 예약만으로는 잔여 횟수가 줄지 않는다.
    stored = client.get(
        _pass_url(academy["id"], student["id"], issued["id"])
    ).json()
    assert stored["remaining_sessions"] == 10

    # 시간이 겹쳐도 예약을 허용한다(이번 단계에서는 중복 검사를 하지 않음).
    overlapping = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=day(1) + "T19:30:00",
    )
    assert overlapping["scheduled_end_at"] == day(1) + "T20:20:00"

    # 클라이언트가 종료 시각을 직접 보내면 거부한다.
    rejected = client.post(
        f"/api/academies/{academy['id']}/attendance-records",
        json={
            "student_id": student["id"],
            "student_pass_id": issued["id"],
            "class_name": "직접 계산",
            "scheduled_at": day(1) + "T20:00:00",
            "scheduled_end_at": day(1) + "T23:00:00",
        },
    )
    assert rejected.status_code == 422


def test_reservation_rejects_expired_or_exhausted_pass(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    single = ledger.pass_type(
        academy["id"],
        name="1회권",
        total_sessions=1,
        validity_days=30,
    )
    student = ledger.student(academy["id"])
    issued = ledger.issue(
        academy["id"],
        student["id"],
        single["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )

    expired = client.post(
        f"/api/academies/{academy['id']}/attendance-records",
        json={
            "student_id": student["id"],
            "student_pass_id": issued["id"],
            "class_name": "만료 후 수업",
            "scheduled_at": day(60) + "T10:00:00",
        },
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "PASS_EXPIRED"

    record = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    ledger.check_in(academy["id"], record["id"])
    ledger.check_out(academy["id"], record["id"])

    exhausted = client.post(
        f"/api/academies/{academy['id']}/attendance-records",
        json={
            "student_id": student["id"],
            "student_pass_id": issued["id"],
            "class_name": "잔여 없음",
            "scheduled_at": day(1) + "T10:00:00",
        },
    )
    assert exhausted.status_code == 409
    assert (
        exhausted.json()["error"]["code"] == "INSUFFICIENT_REMAINING_SESSIONS"
    )


def test_check_in_then_check_out_deducts_once(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=10)
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])
    record = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    base = f"/api/academies/{academy['id']}/attendance-records/{record['id']}"

    checked_in = ledger.check_in(academy["id"], record["id"])
    assert checked_in["status"] == "CHECKED_IN"
    assert checked_in["checked_in_at"] is not None
    assert checked_in["checked_out_at"] is None
    assert checked_in["session_delta"] == 0
    # 체크인만으로는 차감하지 않는다.
    assert checked_in["remaining_sessions"] == 10
    assert client.get(
        _pass_url(academy["id"], student["id"], issued["id"])
    ).json()["remaining_sessions"] == 10

    duplicate = client.post(base + "/check-in", json={})
    assert duplicate.status_code == 409
    assert (
        duplicate.json()["error"]["code"] == "ATTENDANCE_ALREADY_CHECKED_IN"
    )

    checked_out = ledger.check_out(academy["id"], record["id"])
    assert checked_out["status"] == "COMPLETED"
    assert checked_out["session_delta"] == -1
    assert checked_out["checked_out_at"] is not None
    assert checked_out["completed_at"] is not None
    assert checked_out["checked_in_at"] == checked_in["checked_in_at"]
    assert checked_out["remaining_sessions"] == 9

    # 중복 퇴실은 막히고 두 번 차감되지 않는다.
    repeated = client.post(base + "/check-out", json={})
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "ATTENDANCE_ALREADY_COMPLETED"
    assert client.get(
        _pass_url(academy["id"], student["id"], issued["id"])
    ).json()["remaining_sessions"] == 9


def test_check_in_and_check_out_reject_invalid_states(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])

    reserved = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    reserved_url = (
        f"/api/academies/{academy['id']}/attendance-records/{reserved['id']}"
    )
    # 체크인하지 않은 예약은 퇴실할 수 없다.
    not_checked_in = client.post(reserved_url + "/check-out", json={})
    assert not_checked_in.status_code == 409
    assert (
        not_checked_in.json()["error"]["code"] == "ATTENDANCE_NOT_CHECKED_IN"
    )

    cancelled = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    ledger.cancel(academy["id"], cancelled["id"])
    cancelled_check_in = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{cancelled['id']}/check-in"
        ),
        json={},
    )
    assert cancelled_check_in.status_code == 409
    assert (
        cancelled_check_in.json()["error"]["code"] == "ATTENDANCE_NOT_RESERVED"
    )

    completed = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    ledger.complete(academy["id"], completed["id"])
    completed_check_in = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{completed['id']}/check-in"
        ),
        json={},
    )
    assert completed_check_in.status_code == 409
    assert (
        completed_check_in.json()["error"]["code"] == "ATTENDANCE_NOT_RESERVED"
    )


def test_checked_in_reservation_cannot_be_cancelled_by_member(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])
    record = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    ledger.check_in(academy["id"], record["id"])

    rejected = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{record['id']}/cancel"
        ),
        json={},
    )
    assert rejected.status_code == 409
    assert (
        rejected.json()["error"]["code"] == "ATTENDANCE_ALREADY_CHECKED_IN"
    )


def test_owner_complete_supports_reserved_and_checked_in(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=10)
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])

    from_reserved = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    completed = ledger.complete(academy["id"], from_reserved["id"])
    assert completed["status"] == "COMPLETED"
    # 예약에서 바로 완료하면 완료 시각을 체크인 시각으로도 기록한다.
    assert completed["checked_in_at"] == completed["checked_out_at"]

    from_checked_in = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    checked_in = ledger.check_in(academy["id"], from_checked_in["id"])
    completed_second = ledger.complete(academy["id"], from_checked_in["id"])
    assert completed_second["status"] == "COMPLETED"
    # 회원이 체크인한 시각은 그대로 유지된다.
    assert completed_second["checked_in_at"] == checked_in["checked_in_at"]
    assert completed_second["checked_out_at"] is not None

    assert client.get(
        _pass_url(academy["id"], student["id"], issued["id"])
    ).json()["remaining_sessions"] == 8


def test_restore_clears_check_in_and_out_times(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"], total_sessions=10)
    student = ledger.student(academy["id"])
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])
    record = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )
    ledger.check_in(academy["id"], record["id"])
    ledger.check_out(academy["id"], record["id"])

    restored = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{record['id']}/restore"
        ),
        json={"reason": "퇴실 처리 실수"},
    )
    assert restored.status_code == 200
    body = restored.json()
    assert body["status"] == "CANCELLED"
    assert body["session_delta"] == 0
    assert body["checked_in_at"] is None
    assert body["checked_out_at"] is None
    assert body["completed_at"] is None
    assert client.get(
        _pass_url(academy["id"], student["id"], issued["id"])
    ).json()["remaining_sessions"] == 10


def test_portal_summary_and_reservation_list(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(
        academy["id"],
        total_sessions=10,
        validity_days=60,
        session_duration_minutes=50,
    )
    student = ledger.student(academy["id"], name="김민지")
    issued = ledger.issue(
        academy["id"],
        student["id"],
        pass_type["id"],
        purchased_at=moment(0),
        started_at=moment(0),
    )
    upcoming = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        class_name="그룹 필라테스",
        scheduled_at=day(1) + "T19:00:00",
    )
    ongoing = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        class_name="오늘 수업",
        scheduled_at=moment(0),
    )
    ledger.check_in(academy["id"], ongoing["id"])
    ledger.inquiry(academy["id"], student["id"], category="PASS")

    summary = client.get(
        f"/api/academies/{academy['id']}/students/{student['id']}"
        "/portal-summary"
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body["student"]["name"] == "김민지"
    assert body["student"]["is_active"] is True
    assert body["passes"]["total_count"] == 1
    assert body["passes"]["available_count"] == 1
    assert body["passes"]["total_remaining_sessions"] == 10
    assert body["passes"]["nearest_expire_date"] == day(60)
    assert body["attendance"]["today_count"] == 1
    assert body["attendance"]["next_reservation"]["id"] == upcoming["id"]
    assert (
        body["attendance"]["next_reservation"]["scheduled_end_at"]
        == day(1) + "T19:50:00"
    )
    assert body["attendance"]["currently_checked_in"]["id"] == ongoing["id"]
    assert len(body["attendance"]["recent_items"]) == 2
    assert body["inquiries"]["open_count"] == 1

    reservations = client.get(
        f"/api/academies/{academy['id']}/students/{student['id']}"
        "/reservations",
        params={"upcoming_only": True, "sort": "scheduled_at", "order": "asc"},
    )
    assert reservations.status_code == 200
    items = reservations.json()["items"]
    assert [item["id"] for item in items] == [ongoing["id"], upcoming["id"]]
    assert items[0]["status"] == "CHECKED_IN"
    assert items[0]["remaining_sessions"] == 10
    assert items[0]["pass_type_name"] == pass_type["name"]
    assert items[1]["scheduled_end_at"] == day(1) + "T19:50:00"

    filtered = client.get(
        f"/api/academies/{academy['id']}/students/{student['id']}"
        "/reservations",
        params={"status": "CHECKED_IN"},
    ).json()
    assert filtered["pagination"]["total"] == 1


def test_member_endpoints_are_scoped_to_academy_and_student(
    client: TestClient,
    ledger: Ledger,
) -> None:
    first = ledger.academy("첫 번째 학원")
    second = ledger.academy("두 번째 학원")
    student = ledger.student(first["id"], name="A 회원")

    hidden = client.get(
        f"/api/academies/{second['id']}/students/{student['id']}"
        "/portal-summary"
    )
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "STUDENT_NOT_FOUND"

    missing = client.get(
        f"/api/academies/{first['id']}/students/9999/reservations"
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "STUDENT_NOT_FOUND"


def test_member_portal_operation_ids(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        (
            "/api/academies/{academy_id}/students/{student_id}/portal-summary",
            "get",
        ): "get_student_portal_summary",
        (
            "/api/academies/{academy_id}/students/{student_id}/reservations",
            "get",
        ): "list_student_reservations",
        (
            "/api/academies/{academy_id}/attendance-records/"
            "{attendance_record_id}/check-in",
            "post",
        ): "check_in_attendance",
        (
            "/api/academies/{academy_id}/attendance-records/"
            "{attendance_record_id}/check-out",
            "post",
        ): "check_out_attendance",
        (
            "/api/academies/{academy_id}/students/{student_id}/passes",
            "post",
        ): "issue_student_pass",
        (
            "/api/academies/{academy_id}/students/{student_id}/passes/"
            "{student_pass_id}",
            "delete",
        ): "delete_student_pass",
    }
    for (path, method), operation_id in expected.items():
        assert paths[path][method]["operationId"] == operation_id

    # 체크인·퇴실 응답 스키마가 OpenAPI 에 노출된다.
    check_in_path = (
        "/api/academies/{academy_id}/attendance-records/"
        "{attendance_record_id}/check-in"
    )
    schema = paths[check_in_path]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert schema["$ref"].endswith("AttendanceActionResponse")
