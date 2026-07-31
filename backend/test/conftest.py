"""신규 조회 API 테스트가 공유하는 픽스처와 장부 생성 도우미."""

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from database import db_connector
from init_db import init_db
from main import app


TEST_DATABASE_PATH = Path(__file__).resolve().parent / "test_reporting.db"


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


def day(offset: int) -> str:
    """오늘 기준 상대 날짜(YYYY-MM-DD). 테스트를 날짜에 독립적으로 만든다."""
    return (date.today() + timedelta(days=offset)).isoformat()


def moment(offset_days: int, hour: int = 10) -> str:
    """오늘 기준 상대 일시(ISO-8601)."""
    target = datetime.now().replace(
        hour=hour,
        minute=0,
        second=0,
        microsecond=0,
    ) + timedelta(days=offset_days)
    return target.isoformat()


class Ledger:
    """테스트용 장부 데이터를 만드는 얇은 도우미."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def academy(self, name: str = "테스트 아카데미") -> dict:
        response = self.client.post("/api/academies", json={"name": name})
        assert response.status_code == 201, response.text
        return response.json()

    def pass_type(
        self,
        academy_id: int,
        *,
        name: str = "10회권",
        total_sessions: int = 10,
        validity_days: int = 90,
        price: int = 300000,
    ) -> dict:
        response = self.client.post(
            f"/api/academies/{academy_id}/pass-types",
            json={
                "name": name,
                "total_sessions": total_sessions,
                "validity_days": validity_days,
                "price": price,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def student(
        self,
        academy_id: int,
        *,
        name: str = "홍길동",
        phone: str | None = None,
    ) -> dict:
        payload: dict = {"name": name}
        if phone is not None:
            payload["phone"] = phone
        response = self.client.post(
            f"/api/academies/{academy_id}/students",
            json=payload,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def issue(
        self,
        academy_id: int,
        student_id: int,
        pass_type_id: int,
        *,
        purchased_at: str | None = None,
        started_at: str | None = None,
    ) -> dict:
        payload: dict = {"pass_type_id": pass_type_id}
        if purchased_at is not None:
            payload["purchased_at"] = purchased_at
        if started_at is not None:
            payload["started_at"] = started_at
        response = self.client.post(
            f"/api/academies/{academy_id}/students/{student_id}/passes",
            json=payload,
        )
        assert response.status_code == 201, response.text
        return response.json()

    def reserve(
        self,
        academy_id: int,
        student_id: int,
        student_pass_id: int,
        *,
        class_name: str = "그룹 필라테스",
        scheduled_at: str | None = None,
    ) -> dict:
        response = self.client.post(
            f"/api/academies/{academy_id}/attendance-records",
            json={
                "student_id": student_id,
                "student_pass_id": student_pass_id,
                "class_name": class_name,
                "scheduled_at": scheduled_at or moment(0),
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    def complete(self, academy_id: int, attendance_record_id: int) -> dict:
        response = self.client.post(
            (
                f"/api/academies/{academy_id}/attendance-records/"
                f"{attendance_record_id}/complete"
            ),
            json={},
        )
        assert response.status_code == 200, response.text
        return response.json()

    def cancel(self, academy_id: int, attendance_record_id: int) -> dict:
        response = self.client.post(
            (
                f"/api/academies/{academy_id}/attendance-records/"
                f"{attendance_record_id}/cancel"
            ),
            json={},
        )
        assert response.status_code == 200, response.text
        return response.json()

    def corrupt_remaining_sessions(
        self,
        student_pass_id: int,
        remaining_sessions: int,
    ) -> None:
        """정합성 점검 테스트를 위해 잔여 횟수를 의도적으로 어긋나게 한다.

        API로는 만들 수 없는 상태이므로 테스트에서만 직접 수정한다.
        """
        connection = db_connector._connect()
        try:
            with connection:
                connection.execute(
                    """
                    UPDATE student_passes
                    SET remaining_sessions = ?
                    WHERE id = ?
                    """,
                    (remaining_sessions, student_pass_id),
                )
        finally:
            connection.close()


@pytest.fixture
def ledger(client: TestClient) -> Ledger:
    return Ledger(client)
