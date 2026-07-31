"""수강권 장부 REST API 통합 테스트."""

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from database import db_connector
from init_db import init_db
from main import app


TEST_DATABASE_PATH = Path(__file__).resolve().parent / "test_api.db"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """각 테스트에 빈 전용 SQLite와 API 클라이언트를 제공한다."""
    init_db(TEST_DATABASE_PATH)
    monkeypatch.setattr(
        db_connector,
        "DATABASE_PATH",
        TEST_DATABASE_PATH,
    )
    with TestClient(app) as test_client:
        yield test_client
    for path in (
        TEST_DATABASE_PATH,
        Path(f"{TEST_DATABASE_PATH}-journal"),
        Path(f"{TEST_DATABASE_PATH}-shm"),
        Path(f"{TEST_DATABASE_PATH}-wal"),
    ):
        path.unlink(missing_ok=True)


def _create_academy(
    client: TestClient,
    name: str = "테스트 아카데미",
) -> dict:
    response = client.post(
        "/api/academies",
        json={"name": name, "phone": "02-1234-5678"},
    )
    assert response.status_code == 201
    return response.json()


def _create_pass_type(
    client: TestClient,
    academy_id: int,
    *,
    name: str = "10회권",
    total_sessions: int = 10,
    validity_days: int = 90,
) -> dict:
    response = client.post(
        f"/api/academies/{academy_id}/pass-types",
        json={
            "name": name,
            "total_sessions": total_sessions,
            "validity_days": validity_days,
            "price": 300000,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_student(
    client: TestClient,
    academy_id: int,
    *,
    name: str = "홍길동",
    phone: str = "010-0000-0000",
) -> dict:
    response = client.post(
        f"/api/academies/{academy_id}/students",
        json={"name": name, "phone": phone},
    )
    assert response.status_code == 201
    return response.json()


def _issue_pass(
    client: TestClient,
    academy_id: int,
    student_id: int,
    pass_type_id: int,
) -> dict:
    response = client.post(
        (
            f"/api/academies/{academy_id}/students/"
            f"{student_id}/passes"
        ),
        json={
            "pass_type_id": pass_type_id,
            "purchased_at": "2026-07-30T10:00:00",
            "started_at": "2026-07-30T10:00:00",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_attendance(
    client: TestClient,
    academy_id: int,
    student_id: int,
    student_pass_id: int,
) -> dict:
    response = client.post(
        f"/api/academies/{academy_id}/attendance-records",
        json={
            "student_id": student_id,
            "student_pass_id": student_pass_id,
            "class_name": "오전 수업",
            "scheduled_at": "2026-08-01T10:00:00",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_health_openapi_and_endpoint_policy(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "database": "connected",
    }

    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/academies" in paths
    attendance_path = (
        "/api/academies/{academy_id}/attendance-records/"
        "{attendance_record_id}"
    )
    assert "delete" not in paths[attendance_path]
    assert client.get("/docs").status_code == 200


def test_health_reports_database_connection_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unavailable_path = (
        Path(__file__).resolve().parent
        / "missing_database_directory"
        / "unavailable.db"
    )
    monkeypatch.setattr(
        db_connector,
        "DATABASE_PATH",
        unavailable_path,
    )
    response = client.get("/api/health")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_academy_pass_type_student_crud_and_isolation(
    client: TestClient,
) -> None:
    first = _create_academy(client, "첫 번째 학원")
    second = _create_academy(client, "두 번째 학원")
    pass_type = _create_pass_type(client, first["id"])
    student = _create_student(client, first["id"])

    duplicate_pass = client.post(
        f"/api/academies/{first['id']}/pass-types",
        json={
            "name": pass_type["name"],
            "total_sessions": 5,
            "validity_days": 30,
            "price": 100000,
        },
    )
    assert duplicate_pass.status_code == 409
    assert (
        duplicate_pass.json()["error"]["code"]
        == "DUPLICATE_PASS_TYPE_NAME"
    )

    duplicate_student = client.post(
        f"/api/academies/{first['id']}/students",
        json={"name": "다른 이름", "phone": student["phone"]},
    )
    assert duplicate_student.status_code == 409
    assert (
        duplicate_student.json()["error"]["code"]
        == "DUPLICATE_STUDENT_PHONE"
    )

    same_phone_other_academy = _create_student(
        client,
        second["id"],
        name="다른 학원 회원",
        phone=student["phone"],
    )
    assert same_phone_other_academy["academy_id"] == second["id"]

    hidden = client.get(
        (
            f"/api/academies/{second['id']}/students/"
            f"{student['id']}"
        )
    )
    assert hidden.status_code == 404

    updated = client.patch(
        f"/api/academies/{first['id']}",
        json={"address": "서울특별시"},
    )
    assert updated.status_code == 200
    assert updated.json()["address"] == "서울특별시"


def test_issuance_snapshot_and_pass_type_deletion(
    client: TestClient,
) -> None:
    academy = _create_academy(client)
    pass_type = _create_pass_type(client, academy["id"])
    student = _create_student(client, academy["id"])
    issued = _issue_pass(
        client,
        academy["id"],
        student["id"],
        pass_type["id"],
    )

    assert issued["pass_type_id_snapshot"] == pass_type["id"]
    assert issued["pass_type_name_snapshot"] == pass_type["name"]
    assert issued["remaining_sessions"] == 10
    assert issued["expire_date"] == "2026-10-28"
    assert issued["student_expire_date"] == "2026-10-28"

    deleted = client.delete(
        (
            f"/api/academies/{academy['id']}/pass-types/"
            f"{pass_type['id']}"
        )
    )
    assert deleted.status_code == 204

    existing_pass = client.get(
        (
            f"/api/academies/{academy['id']}/students/"
            f"{student['id']}/passes/{issued['id']}"
        )
    )
    assert existing_pass.status_code == 200
    body = existing_pass.json()
    assert body["pass_type_id"] is None
    assert body["pass_type_exists"] is False
    assert body["pass_type_name_snapshot"] == pass_type["name"]


def test_attendance_complete_restore_transaction(
    client: TestClient,
) -> None:
    academy = _create_academy(client)
    pass_type = _create_pass_type(
        client,
        academy["id"],
        total_sessions=1,
    )
    student = _create_student(client, academy["id"])
    issued = _issue_pass(
        client,
        academy["id"],
        student["id"],
        pass_type["id"],
    )
    attendance = _create_attendance(
        client,
        academy["id"],
        student["id"],
        issued["id"],
    )
    assert attendance["status"] == "RESERVED"
    assert attendance["session_delta"] == 0

    completed = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}/complete"
        ),
        json={"completed_at": "2026-08-01T11:00:00"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["session_delta"] == -1

    after_complete = client.get(
        (
            f"/api/academies/{academy['id']}/students/"
            f"{student['id']}/passes/{issued['id']}"
        )
    )
    assert after_complete.json()["remaining_sessions"] == 0

    duplicate = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}/complete"
        ),
        json={},
    )
    assert duplicate.status_code == 409
    assert (
        duplicate.json()["error"]["code"]
        == "ATTENDANCE_ALREADY_COMPLETED"
    )
    assert client.get(
        (
            f"/api/academies/{academy['id']}/students/"
            f"{student['id']}/passes/{issued['id']}"
        )
    ).json()["remaining_sessions"] == 0

    restored = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}/restore"
        ),
        json={"reason": "완료 처리 실수"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "CANCELLED"
    assert restored.json()["session_delta"] == 0
    assert "완료 처리 실수" in restored.json()["memo"]
    assert client.get(
        (
            f"/api/academies/{academy['id']}/students/"
            f"{student['id']}/passes/{issued['id']}"
        )
    ).json()["remaining_sessions"] == 1


def test_reservation_cancel_keeps_remaining_sessions(
    client: TestClient,
) -> None:
    academy = _create_academy(client)
    pass_type = _create_pass_type(client, academy["id"])
    student = _create_student(client, academy["id"])
    issued = _issue_pass(
        client,
        academy["id"],
        student["id"],
        pass_type["id"],
    )
    attendance = _create_attendance(
        client,
        academy["id"],
        student["id"],
        issued["id"],
    )

    updated = client.patch(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}"
        ),
        json={"class_name": "변경된 수업"},
    )
    assert updated.status_code == 200
    assert updated.json()["class_name"] == "변경된 수업"

    cancelled = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}/cancel"
        ),
        json={"memo": "회원 요청"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["session_delta"] == 0
    assert client.get(
        (
            f"/api/academies/{academy['id']}/students/"
            f"{student['id']}/passes/{issued['id']}"
        )
    ).json()["remaining_sessions"] == issued["remaining_sessions"]

    duplicate = client.post(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}/cancel"
        ),
        json={},
    )
    assert duplicate.status_code == 409
    assert (
        duplicate.json()["error"]["code"]
        == "ATTENDANCE_ALREADY_CANCELLED"
    )


def test_student_pass_deletion_keeps_attendance_snapshots(
    client: TestClient,
) -> None:
    """잔여 횟수가 남아 있어도 삭제되고 수강 기록 스냅샷은 유지된다."""
    academy = _create_academy(client)
    pass_type = _create_pass_type(
        client,
        academy["id"],
        total_sessions=1,
    )
    student = _create_student(client, academy["id"])
    issued = _issue_pass(
        client,
        academy["id"],
        student["id"],
        pass_type["id"],
    )
    attendance = _create_attendance(
        client,
        academy["id"],
        student["id"],
        issued["id"],
    )
    pass_url = (
        f"/api/academies/{academy['id']}/students/"
        f"{student['id']}/passes/{issued['id']}"
    )
    student_url = (
        f"/api/academies/{academy['id']}/students/{student['id']}"
    )

    assert issued["remaining_sessions"] == 1
    assert client.get(student_url).json()["expire_date"] is not None

    # 남은 횟수가 있어도 삭제할 수 있다(회원 포털 요구사항).
    assert client.delete(pass_url).status_code == 204

    # 남은 수강권이 없으므로 회원 만료일은 비워진다.
    assert client.get(student_url).json()["expire_date"] is None

    preserved = client.get(
        (
            f"/api/academies/{academy['id']}/attendance-records/"
            f"{attendance['id']}"
        )
    )
    assert preserved.status_code == 200
    assert preserved.json()["student_pass_id"] is None
    assert (
        preserved.json()["pass_type_name_snapshot"]
        == pass_type["name"]
    )


def test_deleting_academy_cascades_attendance_records(
    client: TestClient,
) -> None:
    academy = _create_academy(client)
    pass_type = _create_pass_type(client, academy["id"])
    student = _create_student(client, academy["id"])
    issued = _issue_pass(
        client,
        academy["id"],
        student["id"],
        pass_type["id"],
    )
    attendance = _create_attendance(
        client,
        academy["id"],
        student["id"],
        issued["id"],
    )

    deleted = client.delete(f"/api/academies/{academy['id']}")
    assert deleted.status_code == 204

    connection = sqlite3.connect(TEST_DATABASE_PATH)
    try:
        attendance_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM attendance_records
            WHERE id = ?
            """,
            (attendance["id"],),
        ).fetchone()[0]
    finally:
        connection.close()
    assert attendance_count == 0


def test_pagination_filter_sort_and_validation(
    client: TestClient,
) -> None:
    _create_academy(client, "가 학원")
    _create_academy(client, "나 학원")
    _create_academy(client, "다 학원")

    page = client.get(
        "/api/academies",
        params={
            "limit": 2,
            "offset": 1,
            "sort": "name",
            "order": "desc",
        },
    )
    assert page.status_code == 200
    assert page.json()["pagination"] == {
        "limit": 2,
        "offset": 1,
        "total": 3,
    }
    assert [item["name"] for item in page.json()["items"]] == [
        "나 학원",
        "가 학원",
    ]

    invalid_sort = client.get(
        "/api/academies",
        params={"sort": "DROP TABLE academies"},
    )
    assert invalid_sort.status_code == 422
    assert client.get(
        "/api/academies",
        params={"limit": 101},
    ).status_code == 422
