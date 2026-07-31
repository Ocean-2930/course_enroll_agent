"""문의(회원 등록 · 아카데미 답변) API 통합 테스트."""

from fastapi.testclient import TestClient

from conftest import Ledger, moment


def _student_inquiry_url(
    academy_id: int,
    student_id: int,
    inquiry_id: int | None = None,
) -> str:
    base = f"/api/academies/{academy_id}/students/{student_id}/inquiries"
    return base if inquiry_id is None else f"{base}/{inquiry_id}"


def test_create_inquiry_stores_first_message_and_links(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    student = ledger.student(academy["id"], name="김민지")
    issued = ledger.issue(academy["id"], student["id"], pass_type["id"])
    record = ledger.reserve(
        academy["id"],
        student["id"],
        issued["id"],
        scheduled_at=moment(0),
    )

    inquiry = ledger.inquiry(
        academy["id"],
        student["id"],
        category="DEDUCTION_ERROR",
        title="수강 횟수가 잘못 차감된 것 같습니다.",
        message="오늘 수업이 두 번 차감된 것 같습니다.",
        related_student_pass_id=issued["id"],
        related_attendance_record_id=record["id"],
    )

    assert inquiry["status"] == "OPEN"
    assert inquiry["category"] == "DEDUCTION_ERROR"
    assert inquiry["student_name_snapshot"] == "김민지"
    assert inquiry["closed_at"] is None
    assert inquiry["message_count"] == 1
    assert len(inquiry["messages"]) == 1
    assert inquiry["messages"][0]["sender_type"] == "STUDENT"
    assert (
        inquiry["messages"][0]["message"] == "오늘 수업이 두 번 차감된 것 같습니다."
    )
    assert inquiry["related_student_pass"]["id"] == issued["id"]
    assert inquiry["related_student_pass"]["remaining_sessions"] == 10
    assert inquiry["related_attendance_record"]["id"] == record["id"]


def test_inquiry_rejects_other_students_resources(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    pass_type = ledger.pass_type(academy["id"])
    owner = ledger.student(academy["id"], name="본인", phone="010-1111-1111")
    other = ledger.student(academy["id"], name="타인", phone="010-2222-2222")
    other_pass = ledger.issue(academy["id"], other["id"], pass_type["id"])
    other_record = ledger.reserve(
        academy["id"],
        other["id"],
        other_pass["id"],
        scheduled_at=moment(0),
    )

    rejected_pass = client.post(
        _student_inquiry_url(academy["id"], owner["id"]),
        json={
            "category": "PASS",
            "title": "남의 수강권 연결",
            "message": "확인 부탁드립니다.",
            "related_student_pass_id": other_pass["id"],
        },
    )
    assert rejected_pass.status_code == 400
    assert (
        rejected_pass.json()["error"]["code"] == "STUDENT_PASS_OWNER_MISMATCH"
    )

    rejected_record = client.post(
        _student_inquiry_url(academy["id"], owner["id"]),
        json={
            "category": "ATTENDANCE",
            "title": "남의 수강 기록 연결",
            "message": "확인 부탁드립니다.",
            "related_attendance_record_id": other_record["id"],
        },
    )
    assert rejected_record.status_code == 400
    assert (
        rejected_record.json()["error"]["code"]
        == "ATTENDANCE_RECORD_OWNER_MISMATCH"
    )

    # 실패한 문의는 저장되지 않는다.
    listed = client.get(
        _student_inquiry_url(academy["id"], owner["id"])
    ).json()
    assert listed["pagination"]["total"] == 0

    invalid_category = client.post(
        _student_inquiry_url(academy["id"], owner["id"]),
        json={
            "category": "UNKNOWN",
            "title": "잘못된 유형",
            "message": "확인 부탁드립니다.",
        },
    )
    assert invalid_category.status_code == 422


def test_inquiry_conversation_flow_and_status_changes(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    student = ledger.student(academy["id"], name="김민지")
    inquiry = ledger.inquiry(
        academy["id"],
        student["id"],
        category="EXTENSION",
        title="기간 연장 문의",
        message="출장 때문에 연장이 가능할까요?",
    )
    inquiry_id = inquiry["id"]

    answered = client.post(
        f"/api/academies/{academy['id']}/inquiries/{inquiry_id}/messages",
        json={"message": "네, 2주까지 연장 가능합니다."},
    )
    assert answered.status_code == 201
    assert answered.json()["status"] == "ANSWERED"
    assert answered.json()["messages"][-1]["sender_type"] == "ACADEMY"

    # 회원이 다시 물으면 답변 대기(OPEN) 상태로 돌아간다.
    replied = client.post(
        _student_inquiry_url(academy["id"], student["id"], inquiry_id)
        + "/messages",
        json={"message": "연장 신청은 어디서 하나요?"},
    )
    assert replied.status_code == 201
    assert replied.json()["status"] == "OPEN"

    detail = client.get(
        _student_inquiry_url(academy["id"], student["id"], inquiry_id)
    ).json()
    assert [message["sender_type"] for message in detail["messages"]] == [
        "STUDENT",
        "ACADEMY",
        "STUDENT",
    ]
    assert detail["message_count"] == 3
    assert detail["last_message_at"] is not None

    closed = client.post(
        _student_inquiry_url(academy["id"], student["id"], inquiry_id)
        + "/close",
        json={},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"] is not None

    for url in (
        _student_inquiry_url(academy["id"], student["id"], inquiry_id)
        + "/messages",
        f"/api/academies/{academy['id']}/inquiries/{inquiry_id}/messages",
    ):
        blocked = client.post(url, json={"message": "추가 메시지"})
        assert blocked.status_code == 409
        assert blocked.json()["error"]["code"] == "INQUIRY_CLOSED"


def test_inquiry_listing_filters_and_isolation(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    other_academy = ledger.academy("다른 학원")
    first = ledger.student(academy["id"], name="회원1", phone="010-1111-0001")
    second = ledger.student(academy["id"], name="회원2", phone="010-1111-0002")
    first_inquiry = ledger.inquiry(
        academy["id"],
        first["id"],
        category="FACILITY",
        title="사물함 문의",
    )
    ledger.inquiry(
        academy["id"],
        second["id"],
        category="REFUND",
        title="환불 규정 문의",
    )

    mine = client.get(_student_inquiry_url(academy["id"], first["id"])).json()
    assert mine["pagination"]["total"] == 1
    assert mine["items"][0]["title"] == "사물함 문의"

    filtered = client.get(
        _student_inquiry_url(academy["id"], first["id"]),
        params={"category": "REFUND"},
    ).json()
    assert filtered["pagination"]["total"] == 0

    # 다른 회원의 문의는 상세 조회할 수 없다.
    forbidden = client.get(
        _student_inquiry_url(academy["id"], second["id"], first_inquiry["id"])
    )
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "INQUIRY_NOT_FOUND"

    # 사업자는 아카데미 전체 문의를 본다.
    academy_view = client.get(
        f"/api/academies/{academy['id']}/inquiries"
    ).json()
    assert academy_view["pagination"]["total"] == 2

    scoped = client.get(
        f"/api/academies/{academy['id']}/inquiries",
        params={"student_id": second["id"]},
    ).json()
    assert scoped["pagination"]["total"] == 1

    # 다른 아카데미에서는 보이지 않는다.
    other_view = client.get(
        f"/api/academies/{other_academy['id']}/inquiries"
    ).json()
    assert other_view["pagination"]["total"] == 0
    assert client.get(
        f"/api/academies/{other_academy['id']}/inquiries/{first_inquiry['id']}"
    ).status_code == 404


def test_inquiry_survives_student_deletion(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    student = ledger.student(academy["id"], name="김민지")
    inquiry = ledger.inquiry(academy["id"], student["id"], title="탈퇴 전 문의")

    deleted = client.delete(
        f"/api/academies/{academy['id']}/students/{student['id']}"
    )
    assert deleted.status_code == 204

    remaining = client.get(
        f"/api/academies/{academy['id']}/inquiries/{inquiry['id']}"
    )
    assert remaining.status_code == 200
    body = remaining.json()
    assert body["student_id"] is None
    assert body["student_name_snapshot"] == "김민지"
    assert len(body["messages"]) == 1


def test_blank_message_is_rejected(
    client: TestClient,
    ledger: Ledger,
) -> None:
    academy = ledger.academy()
    student = ledger.student(academy["id"])
    blank = client.post(
        _student_inquiry_url(academy["id"], student["id"]),
        json={"category": "OTHER", "title": "제목", "message": "   "},
    )
    assert blank.status_code == 422


def test_inquiry_operation_ids(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    student_base = "/api/academies/{academy_id}/students/{student_id}/inquiries"
    academy_base = "/api/academies/{academy_id}/inquiries"
    expected = {
        (student_base, "get"): "list_student_inquiries",
        (student_base, "post"): "create_student_inquiry",
        (student_base + "/{inquiry_id}", "get"): "get_student_inquiry",
        (
            student_base + "/{inquiry_id}/messages",
            "post",
        ): "add_student_inquiry_message",
        (student_base + "/{inquiry_id}/close", "post"): "close_student_inquiry",
        (academy_base, "get"): "list_academy_inquiries",
        (academy_base + "/{inquiry_id}", "get"): "get_academy_inquiry",
        (
            academy_base + "/{inquiry_id}/messages",
            "post",
        ): "add_academy_inquiry_message",
        (academy_base + "/{inquiry_id}/close", "post"): "close_academy_inquiry",
    }
    for (path, method), operation_id in expected.items():
        assert paths[path][method]["operationId"] == operation_id
