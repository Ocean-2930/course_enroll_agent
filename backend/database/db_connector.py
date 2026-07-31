"""API가 사용하는 데이터 저장소 접근 인터페이스를 제공한다.

API 계층은 이 모듈의 함수만 호출한다. SQLite SQL과 트랜잭션은 이 파일
안에 한정하여, 다른 데이터베이스로 전환할 때 이 인터페이스의 구현만
교체할 수 있게 한다.
"""

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
from typing import Any

from database.connection import (
    DATABASE_PATH as DEFAULT_DATABASE_PATH,
    connect_database,
)


DATABASE_PATH = DEFAULT_DATABASE_PATH

ACADEMY_SORT_FIELDS = {
    "id": "id",
    "name": "name",
    "created_at": "created_at",
    "updated_at": "updated_at",
}
PASS_TYPE_SORT_FIELDS = {
    "id": "id",
    "name": "name",
    "price": "price",
    "total_sessions": "total_sessions",
    "validity_days": "validity_days",
    "sort_index": "sort_index",
    "created_at": "created_at",
}
STUDENT_SORT_FIELDS = {
    "id": "id",
    "name": "name",
    "expire_date": "expire_date",
    "created_at": "created_at",
    "updated_at": "updated_at",
}
STUDENT_PASS_SORT_FIELDS = {
    "id": "id",
    "purchased_at": "purchased_at",
    "started_at": "started_at",
    "expire_date": "expire_date",
    "remaining_sessions": "remaining_sessions",
    "created_at": "created_at",
}
ATTENDANCE_SORT_FIELDS = {
    "id": "id",
    "scheduled_at": "scheduled_at",
    "created_at": "created_at",
    "updated_at": "updated_at",
    "status": "status",
    "class_name": "class_name",
}


class DatabaseError(Exception):
    """저장소 계층에서 API로 전달하는 예측 가능한 업무 오류."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = dict(details or {})


def _error(
    status_code: int,
    code: str,
    message: str,
    **details: Any,
) -> DatabaseError:
    return DatabaseError(status_code, code, message, details)


def _connect() -> sqlite3.Connection:
    return connect_database(Path(DATABASE_PATH))


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _add_minutes(moment: str, minutes: int) -> str:
    """ISO-8601 시각에 분을 더한다(예약 종료 시각 계산)."""
    return (
        datetime.fromisoformat(moment) + timedelta(minutes=minutes)
    ).replace(microsecond=0).isoformat()


def _as_iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _normalized_values(values: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _as_iso(value) for key, value in values.items()}


def _require_update(
    values: Mapping[str, Any],
    allowed_fields: set[str],
) -> dict[str, Any]:
    normalized = _normalized_values(values)
    if not normalized:
        raise _error(
            400,
            "EMPTY_UPDATE",
            "수정할 필드가 없습니다.",
        )
    unknown_fields = sorted(set(normalized) - allowed_fields)
    if unknown_fields:
        raise _error(
            422,
            "INVALID_UPDATE_FIELDS",
            "수정할 수 없는 필드가 포함되어 있습니다.",
            fields=unknown_fields,
        )
    return normalized


def _sort_clause(
    sort: str,
    order: str,
    allowed_fields: Mapping[str, str],
) -> str:
    if sort not in allowed_fields:
        raise _error(
            422,
            "INVALID_SORT_FIELD",
            "허용되지 않은 정렬 필드입니다.",
            sort=sort,
        )
    if order not in {"asc", "desc"}:
        raise _error(
            422,
            "INVALID_SORT_ORDER",
            "정렬 방향은 asc 또는 desc여야 합니다.",
            order=order,
        )
    return f"{allowed_fields[sort]} {order.upper()}"


def _page(
    connection: sqlite3.Connection,
    select_sql: str,
    count_sql: str,
    parameters: Sequence[Any],
    limit: int,
    offset: int,
) -> dict[str, Any]:
    rows = connection.execute(
        f"{select_sql} LIMIT ? OFFSET ?",
        (*parameters, limit, offset),
    ).fetchall()
    total = connection.execute(count_sql, parameters).fetchone()[0]
    return {
        "items": [dict(row) for row in rows],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }


def _get_academy_row(
    connection: sqlite3.Connection,
    academy_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM academies WHERE id = ?",
        (academy_id,),
    ).fetchone()
    if row is None:
        raise _error(
            404,
            "ACADEMY_NOT_FOUND",
            "아카데미를 찾을 수 없습니다.",
            academy_id=academy_id,
        )
    return row


def _get_student_row(
    connection: sqlite3.Connection,
    academy_id: int,
    student_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM students
        WHERE id = ? AND academy_id = ?
        """,
        (student_id, academy_id),
    ).fetchone()
    if row is None:
        raise _error(
            404,
            "STUDENT_NOT_FOUND",
            "수강생을 찾을 수 없습니다.",
            academy_id=academy_id,
            student_id=student_id,
        )
    return row


def _get_pass_type_row(
    connection: sqlite3.Connection,
    academy_id: int,
    pass_type_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM pass_types
        WHERE id = ? AND academy_id = ?
        """,
        (pass_type_id, academy_id),
    ).fetchone()
    if row is None:
        raise _error(
            404,
            "PASS_TYPE_NOT_FOUND",
            "수강권 종류를 찾을 수 없습니다.",
            academy_id=academy_id,
            pass_type_id=pass_type_id,
        )
    return row


def _get_student_pass_row(
    connection: sqlite3.Connection,
    academy_id: int,
    student_id: int,
    student_pass_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT sp.*
        FROM student_passes AS sp
        JOIN students AS s ON s.id = sp.student_id
        WHERE sp.id = ?
          AND sp.student_id = ?
          AND s.academy_id = ?
        """,
        (student_pass_id, student_id, academy_id),
    ).fetchone()
    if row is None:
        raise _error(
            404,
            "STUDENT_PASS_NOT_FOUND",
            "보유 수강권을 찾을 수 없습니다.",
            academy_id=academy_id,
            student_id=student_id,
            student_pass_id=student_pass_id,
        )
    return row


def _get_attendance_row(
    connection: sqlite3.Connection,
    academy_id: int,
    attendance_record_id: int,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT *
        FROM attendance_records
        WHERE id = ? AND academy_id = ?
        """,
        (attendance_record_id, academy_id),
    ).fetchone()
    if row is None:
        raise _error(
            404,
            "ATTENDANCE_RECORD_NOT_FOUND",
            "수강 기록을 찾을 수 없습니다.",
            academy_id=academy_id,
            attendance_record_id=attendance_record_id,
        )
    return row


def _student_response(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["is_active"] = bool(
        row["expire_date"] is not None and row["expire_date"] >= _today()
    )
    return result


def _student_pass_response(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["used_sessions"] = (
        row["total_sessions"] - row["remaining_sessions"]
    )
    result["is_expired"] = row["expire_date"] < _today()
    result["is_available"] = bool(
        row["remaining_sessions"] > 0
        and row["expire_date"] >= _today()
    )
    result["pass_type_exists"] = row["pass_type_id"] is not None
    return result


def _attendance_response(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["student_name"] = row["student_name_snapshot"]
    result["pass_type_id"] = row["pass_type_id_snapshot"]
    result["pass_type_name"] = row["pass_type_name_snapshot"]
    return result


def health_check() -> dict[str, str]:
    try:
        connection = _connect()
        try:
            connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise _error(
            500,
            "DATABASE_UNAVAILABLE",
            "데이터베이스에 연결할 수 없습니다.",
        ) from error
    return {"status": "ok", "database": "connected"}


def list_academies(
    *,
    name: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    conditions: list[str] = []
    parameters: list[Any] = []
    if name:
        conditions.append("name LIKE ?")
        parameters.append(f"%{name}%")
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    ordering = _sort_clause(sort, order, ACADEMY_SORT_FIELDS)
    connection = _connect()
    try:
        return _page(
            connection,
            f"SELECT * FROM academies{where} ORDER BY {ordering}",
            f"SELECT COUNT(*) FROM academies{where}",
            parameters,
            limit,
            offset,
        )
    finally:
        connection.close()


def create_academy(values: Mapping[str, Any]) -> dict[str, Any]:
    data = _normalized_values(values)
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO academies (name, phone, address)
                VALUES (?, ?, ?)
                """,
                (data["name"], data.get("phone"), data.get("address")),
            )
        return dict(_get_academy_row(connection, cursor.lastrowid))
    finally:
        connection.close()


def get_academy(academy_id: int) -> dict[str, Any]:
    connection = _connect()
    try:
        return dict(_get_academy_row(connection, academy_id))
    finally:
        connection.close()


def update_academy(
    academy_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _require_update(values, {"name", "phone", "address"})
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        assignments = ", ".join(f"{field} = ?" for field in data)
        with connection:
            connection.execute(
                f"""
                UPDATE academies
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (*data.values(), academy_id),
            )
        return dict(_get_academy_row(connection, academy_id))
    finally:
        connection.close()


def delete_academy(academy_id: int) -> None:
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        with connection:
            connection.execute(
                "DELETE FROM academies WHERE id = ?",
                (academy_id,),
            )
    finally:
        connection.close()


def get_academy_summary(academy_id: int) -> dict[str, Any]:
    today = _today()
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        students = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE
                       WHEN expire_date IS NOT NULL AND expire_date >= ?
                       THEN 1 ELSE 0
                   END) AS active
            FROM students
            WHERE academy_id = ?
            """,
            (today, academy_id),
        ).fetchone()
        passes = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM pass_types WHERE academy_id = ?)
                    AS pass_type_count,
                COUNT(sp.id) AS student_pass_count,
                SUM(CASE
                    WHEN sp.remaining_sessions > 0 AND sp.expire_date >= ?
                    THEN 1 ELSE 0
                END) AS available_pass_count,
                COALESCE(SUM(sp.remaining_sessions), 0)
                    AS total_remaining_sessions
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            WHERE s.academy_id = ?
            """,
            (academy_id, today, academy_id),
        ).fetchone()
        attendance = connection.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'RESERVED' THEN 1 ELSE 0 END)
                    AS reserved,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END)
                    AS completed,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END)
                    AS cancelled
            FROM attendance_records
            WHERE academy_id = ? AND substr(scheduled_at, 1, 10) = ?
            """,
            (academy_id, today),
        ).fetchone()
        total_students = students["total"]
        active_students = students["active"] or 0
        return {
            "academy_id": academy_id,
            "students": {
                "total": total_students,
                "active": active_students,
                "inactive": total_students - active_students,
            },
            "passes": {
                key: passes[key] or 0
                for key in (
                    "pass_type_count",
                    "student_pass_count",
                    "available_pass_count",
                    "total_remaining_sessions",
                )
            },
            "today_attendance": {
                key: attendance[key] or 0
                for key in ("reserved", "completed", "cancelled")
            },
        }
    finally:
        connection.close()


def list_pass_types(
    academy_id: int,
    *,
    name: str | None,
    min_price: int | None,
    max_price: int | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        conditions = ["academy_id = ?"]
        parameters: list[Any] = [academy_id]
        if name:
            conditions.append("name LIKE ?")
            parameters.append(f"%{name}%")
        if min_price is not None:
            conditions.append("price >= ?")
            parameters.append(min_price)
        if max_price is not None:
            conditions.append("price <= ?")
            parameters.append(max_price)
        where = f" WHERE {' AND '.join(conditions)}"
        ordering = _sort_clause(sort, order, PASS_TYPE_SORT_FIELDS)
        return _page(
            connection,
            f"SELECT * FROM pass_types{where} ORDER BY {ordering}",
            f"SELECT COUNT(*) FROM pass_types{where}",
            parameters,
            limit,
            offset,
        )
    finally:
        connection.close()


def create_pass_type(
    academy_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _normalized_values(values)
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        # 새 수강권은 해당 아카데미 목록의 맨 뒤 순서로 배치한다.
        next_index = connection.execute(
            """
            SELECT COALESCE(MAX(sort_index), -1) + 1
            FROM pass_types WHERE academy_id = ?
            """,
            (academy_id,),
        ).fetchone()[0]
        try:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO pass_types (
                        academy_id, name, description,
                        total_sessions, validity_days, price,
                        session_duration_minutes, sort_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        academy_id,
                        data["name"],
                        data.get("description"),
                        data["total_sessions"],
                        data["validity_days"],
                        data.get("price", 0),
                        data.get("session_duration_minutes", 60),
                        next_index,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise _error(
                409,
                "DUPLICATE_PASS_TYPE_NAME",
                "같은 아카데미에 동일한 수강권 이름이 있습니다.",
                academy_id=academy_id,
                name=data["name"],
            ) from error
        return dict(
            _get_pass_type_row(connection, academy_id, cursor.lastrowid)
        )
    finally:
        connection.close()


def get_pass_type(
    academy_id: int,
    pass_type_id: int,
) -> dict[str, Any]:
    connection = _connect()
    try:
        return dict(
            _get_pass_type_row(connection, academy_id, pass_type_id)
        )
    finally:
        connection.close()


def update_pass_type(
    academy_id: int,
    pass_type_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _require_update(
        values,
        {
            "name",
            "description",
            "total_sessions",
            "validity_days",
            "price",
            "session_duration_minutes",
            "sort_index",
        },
    )
    connection = _connect()
    try:
        _get_pass_type_row(connection, academy_id, pass_type_id)
        assignments = ", ".join(f"{field} = ?" for field in data)
        try:
            with connection:
                connection.execute(
                    f"""
                    UPDATE pass_types
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND academy_id = ?
                    """,
                    (*data.values(), pass_type_id, academy_id),
                )
        except sqlite3.IntegrityError as error:
            raise _error(
                409,
                "DUPLICATE_PASS_TYPE_NAME",
                "같은 아카데미에 동일한 수강권 이름이 있습니다.",
                academy_id=academy_id,
                name=data.get("name"),
            ) from error
        return dict(
            _get_pass_type_row(connection, academy_id, pass_type_id)
        )
    finally:
        connection.close()


def delete_pass_type(academy_id: int, pass_type_id: int) -> None:
    connection = _connect()
    try:
        _get_pass_type_row(connection, academy_id, pass_type_id)
        with connection:
            connection.execute(
                "DELETE FROM pass_types WHERE id = ? AND academy_id = ?",
                (pass_type_id, academy_id),
            )
    finally:
        connection.close()


def list_students(
    academy_id: int,
    *,
    name: str | None,
    phone: str | None,
    email: str | None,
    active: bool | None,
    expire_from: str | None,
    expire_to: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    today = _today()
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        conditions = ["academy_id = ?"]
        parameters: list[Any] = [academy_id]
        for column, value in (
            ("name", name),
            ("phone", phone),
            ("email", email),
        ):
            if value:
                conditions.append(f"{column} LIKE ?")
                parameters.append(f"%{value}%")
        if active is True:
            conditions.append("expire_date IS NOT NULL AND expire_date >= ?")
            parameters.append(today)
        elif active is False:
            conditions.append("(expire_date IS NULL OR expire_date < ?)")
            parameters.append(today)
        if expire_from:
            conditions.append("expire_date >= ?")
            parameters.append(expire_from)
        if expire_to:
            conditions.append("expire_date <= ?")
            parameters.append(expire_to)
        where = f" WHERE {' AND '.join(conditions)}"
        ordering = _sort_clause(sort, order, STUDENT_SORT_FIELDS)
        page = _page(
            connection,
            f"SELECT * FROM students{where} ORDER BY {ordering}",
            f"SELECT COUNT(*) FROM students{where}",
            parameters,
            limit,
            offset,
        )
        page["items"] = [
            {
                **item,
                "is_active": bool(
                    item["expire_date"] is not None
                    and item["expire_date"] >= today
                ),
            }
            for item in page["items"]
        ]
        return page
    finally:
        connection.close()


def create_student(
    academy_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _normalized_values(values)
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        try:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO students (
                        academy_id, name, phone, email, memo
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        academy_id,
                        data["name"],
                        data.get("phone"),
                        data.get("email"),
                        data.get("memo"),
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise _error(
                409,
                "DUPLICATE_STUDENT_PHONE",
                "같은 아카데미에 동일한 전화번호가 있습니다.",
                academy_id=academy_id,
                phone=data.get("phone"),
            ) from error
        return _student_response(
            _get_student_row(connection, academy_id, cursor.lastrowid)
        )
    finally:
        connection.close()


def get_student(academy_id: int, student_id: int) -> dict[str, Any]:
    connection = _connect()
    try:
        return _student_response(
            _get_student_row(connection, academy_id, student_id)
        )
    finally:
        connection.close()


def update_student(
    academy_id: int,
    student_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _require_update(
        values,
        {"name", "phone", "email", "memo"},
    )
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        assignments = ", ".join(f"{field} = ?" for field in data)
        try:
            with connection:
                connection.execute(
                    f"""
                    UPDATE students
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND academy_id = ?
                    """,
                    (*data.values(), student_id, academy_id),
                )
        except sqlite3.IntegrityError as error:
            raise _error(
                409,
                "DUPLICATE_STUDENT_PHONE",
                "같은 아카데미에 동일한 전화번호가 있습니다.",
                academy_id=academy_id,
                phone=data.get("phone"),
            ) from error
        return _student_response(
            _get_student_row(connection, academy_id, student_id)
        )
    finally:
        connection.close()


def delete_student(academy_id: int, student_id: int) -> None:
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        with connection:
            connection.execute(
                "DELETE FROM students WHERE id = ? AND academy_id = ?",
                (student_id, academy_id),
            )
    finally:
        connection.close()


def get_student_summary(
    academy_id: int,
    student_id: int,
) -> dict[str, Any]:
    today = _today()
    connection = _connect()
    try:
        student = _get_student_row(connection, academy_id, student_id)
        passes = connection.execute(
            """
            SELECT COUNT(*) AS total_count,
                   SUM(CASE
                       WHEN remaining_sessions > 0 AND expire_date >= ?
                       THEN 1 ELSE 0
                   END) AS available_count,
                   COALESCE(SUM(remaining_sessions), 0)
                       AS total_remaining_sessions
            FROM student_passes
            WHERE student_id = ?
            """,
            (today, student_id),
        ).fetchone()
        attendance = connection.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'RESERVED' THEN 1 ELSE 0 END)
                    AS reserved_count,
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END)
                    AS completed_count,
                SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END)
                    AS cancelled_count,
                MAX(CASE
                    WHEN status = 'COMPLETED' THEN completed_at
                END) AS last_completed_at
            FROM attendance_records
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        return {
            "student": {
                "id": student["id"],
                "name": student["name"],
                "expire_date": student["expire_date"],
                "is_active": bool(
                    student["expire_date"] is not None
                    and student["expire_date"] >= today
                ),
            },
            "passes": {
                key: passes[key] or 0
                for key in (
                    "total_count",
                    "available_count",
                    "total_remaining_sessions",
                )
            },
            "attendance": {
                "reserved_count": attendance["reserved_count"] or 0,
                "completed_count": attendance["completed_count"] or 0,
                "cancelled_count": attendance["cancelled_count"] or 0,
                "last_completed_at": attendance["last_completed_at"],
            },
        }
    finally:
        connection.close()


def list_student_passes(
    academy_id: int,
    student_id: int,
    *,
    available: bool | None,
    expired: bool | None,
    pass_type_id: int | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    today = _today()
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        conditions = ["student_id = ?"]
        parameters: list[Any] = [student_id]
        if available is True:
            conditions.append(
                "remaining_sessions > 0 AND expire_date >= ?"
            )
            parameters.append(today)
        elif available is False:
            conditions.append(
                "(remaining_sessions = 0 OR expire_date < ?)"
            )
            parameters.append(today)
        if expired is True:
            conditions.append("expire_date < ?")
            parameters.append(today)
        elif expired is False:
            conditions.append("expire_date >= ?")
            parameters.append(today)
        if pass_type_id is not None:
            conditions.append("pass_type_id_snapshot = ?")
            parameters.append(pass_type_id)
        where = f" WHERE {' AND '.join(conditions)}"
        ordering = _sort_clause(
            sort,
            order,
            STUDENT_PASS_SORT_FIELDS,
        )
        page = _page(
            connection,
            f"SELECT * FROM student_passes{where} ORDER BY {ordering}",
            f"SELECT COUNT(*) FROM student_passes{where}",
            parameters,
            limit,
            offset,
        )
        page["items"] = [
            {
                **item,
                "used_sessions": (
                    item["total_sessions"] - item["remaining_sessions"]
                ),
                "is_expired": item["expire_date"] < today,
                "is_available": bool(
                    item["remaining_sessions"] > 0
                    and item["expire_date"] >= today
                ),
                "pass_type_exists": item["pass_type_id"] is not None,
            }
            for item in page["items"]
        ]
        return page
    finally:
        connection.close()


def list_available_student_passes(
    academy_id: int,
    student_id: int,
) -> list[dict[str, Any]]:
    today = _today()
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        rows = connection.execute(
            """
            SELECT *
            FROM student_passes
            WHERE student_id = ?
              AND remaining_sessions > 0
              AND expire_date >= ?
            ORDER BY expire_date ASC, purchased_at ASC, id ASC
            """,
            (student_id, today),
        ).fetchall()
        return [_student_pass_response(row) for row in rows]
    finally:
        connection.close()


def issue_student_pass(
    academy_id: int,
    student_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _normalized_values(values)
    purchased_at = data.get("purchased_at") or _now()
    started_at = data.get("started_at")
    base_date = date.fromisoformat((started_at or purchased_at)[:10])
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            _get_academy_row(connection, academy_id)
            student = _get_student_row(
                connection,
                academy_id,
                student_id,
            )
            pass_type = connection.execute(
                "SELECT * FROM pass_types WHERE id = ?",
                (data["pass_type_id"],),
            ).fetchone()
            if pass_type is None:
                raise _error(
                    404,
                    "PASS_TYPE_NOT_FOUND",
                    "수강권 종류를 찾을 수 없습니다.",
                    pass_type_id=data["pass_type_id"],
                )
            if pass_type["academy_id"] != academy_id:
                raise _error(
                    400,
                    "PASS_TYPE_ACADEMY_MISMATCH",
                    "다른 아카데미의 수강권은 발급할 수 없습니다.",
                    pass_type_id=pass_type["id"],
                    academy_id=academy_id,
                )
            expire_date = (
                base_date + timedelta(days=pass_type["validity_days"])
            ).isoformat()
            cursor = connection.execute(
                """
                INSERT INTO student_passes (
                    student_id,
                    pass_type_id,
                    pass_type_id_snapshot,
                    pass_type_name_snapshot,
                    total_sessions,
                    remaining_sessions,
                    validity_days_snapshot,
                    price_snapshot,
                    session_duration_minutes_snapshot,
                    purchased_at,
                    started_at,
                    expire_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    pass_type["id"],
                    pass_type["id"],
                    pass_type["name"],
                    pass_type["total_sessions"],
                    pass_type["total_sessions"],
                    pass_type["validity_days"],
                    pass_type["price"],
                    pass_type["session_duration_minutes"],
                    purchased_at,
                    started_at,
                    expire_date,
                ),
            )
            student_expire_date = max(
                value
                for value in (student["expire_date"], expire_date)
                if value is not None
            )
            connection.execute(
                """
                UPDATE students
                SET expire_date = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (student_expire_date, student_id),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        issued_pass = _student_pass_response(
            _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                cursor.lastrowid,
            )
        )
        issued_pass["student_expire_date"] = student_expire_date
        return issued_pass
    finally:
        connection.close()


def get_student_pass(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        return _student_pass_response(
            _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                student_pass_id,
            )
        )
    finally:
        connection.close()


def update_student_pass(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _require_update(values, {"started_at", "expire_date"})
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        _get_student_pass_row(
            connection,
            academy_id,
            student_id,
            student_pass_id,
        )
        assignments = ", ".join(f"{field} = ?" for field in data)
        try:
            with connection:
                connection.execute(
                    f"""
                    UPDATE student_passes
                    SET {assignments}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND student_id = ?
                    """,
                    (*data.values(), student_pass_id, student_id),
                )
        except sqlite3.IntegrityError as error:
            raise _error(
                400,
                "INVALID_STUDENT_PASS_DATES",
                "수강권 날짜 범위가 올바르지 않습니다.",
                student_pass_id=student_pass_id,
            ) from error
        return _student_pass_response(
            _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                student_pass_id,
            )
        )
    finally:
        connection.close()


def delete_student_pass(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
) -> dict[str, Any]:
    """보유 수강권을 물리 삭제하고 학생 만료일을 다시 계산한다.

    잔여 횟수가 남아 있어도 삭제할 수 있다. 수강 기록은 지우지 않고
    `attendance_records.student_pass_id` 만 NULL 이 되며(ON DELETE SET NULL),
    이름·종류 스냅샷은 그대로 남는다. 삭제와 만료일 재계산은 하나의
    트랜잭션으로 처리한다.
    """
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                student_pass_id,
            )
            connection.execute(
                """
                DELETE FROM student_passes
                WHERE id = ? AND student_id = ?
                """,
                (student_pass_id, student_id),
            )
            # 남은 수강권 중 가장 늦은 만료일로 학생 만료일을 다시 맞춘다.
            student_expire_date = connection.execute(
                """
                SELECT MAX(expire_date)
                FROM student_passes
                WHERE student_id = ?
                """,
                (student_id,),
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE students
                SET expire_date = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (student_expire_date, student_id),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        return {
            "student_id": student_id,
            "deleted_student_pass_id": student_pass_id,
            "student_expire_date": student_expire_date,
        }
    finally:
        connection.close()


def list_attendance_records(
    academy_id: int,
    *,
    student_id: int | None,
    student_pass_id: int | None,
    pass_type_id_snapshot: int | None,
    status: str | None,
    class_name: str | None,
    scheduled_from: str | None,
    scheduled_to: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        conditions = ["academy_id = ?"]
        parameters: list[Any] = [academy_id]
        for column, value in (
            ("student_id", student_id),
            ("student_pass_id", student_pass_id),
            ("pass_type_id_snapshot", pass_type_id_snapshot),
            ("status", status),
        ):
            if value is not None:
                conditions.append(f"{column} = ?")
                parameters.append(value)
        if class_name:
            conditions.append("class_name LIKE ?")
            parameters.append(f"%{class_name}%")
        if scheduled_from:
            conditions.append("scheduled_at >= ?")
            parameters.append(scheduled_from)
        if scheduled_to:
            conditions.append("scheduled_at <= ?")
            parameters.append(scheduled_to)
        where = f" WHERE {' AND '.join(conditions)}"
        ordering = _sort_clause(sort, order, ATTENDANCE_SORT_FIELDS)
        page = _page(
            connection,
            f"""
            SELECT *
            FROM attendance_records
            {where}
            ORDER BY {ordering}
            """,
            f"SELECT COUNT(*) FROM attendance_records{where}",
            parameters,
            limit,
            offset,
        )
        page["items"] = [
            {
                **item,
                "student_name": item["student_name_snapshot"],
                "pass_type_id": item["pass_type_id_snapshot"],
                "pass_type_name": item["pass_type_name_snapshot"],
            }
            for item in page["items"]
        ]
        return page
    finally:
        connection.close()


def list_student_attendance_records(
    academy_id: int,
    student_id: int,
    *,
    status: str | None,
    scheduled_from: str | None,
    scheduled_to: str | None,
    limit: int,
    offset: int,
    sort: str = "scheduled_at",
    order: str = "desc",
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
    finally:
        connection.close()
    return list_attendance_records(
        academy_id,
        student_id=student_id,
        student_pass_id=None,
        pass_type_id_snapshot=None,
        status=status,
        class_name=None,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


def list_student_pass_attendance_records(
    academy_id: int,
    student_id: int,
    student_pass_id: int,
    *,
    status: str | None,
    scheduled_from: str | None,
    scheduled_to: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_student_pass_row(
            connection,
            academy_id,
            student_id,
            student_pass_id,
        )
    finally:
        connection.close()
    return list_attendance_records(
        academy_id,
        student_id=student_id,
        student_pass_id=student_pass_id,
        pass_type_id_snapshot=None,
        status=status,
        class_name=None,
        scheduled_from=scheduled_from,
        scheduled_to=scheduled_to,
        limit=limit,
        offset=offset,
        sort="scheduled_at",
        order="desc",
    )


def get_attendance_record(
    academy_id: int,
    attendance_record_id: int,
) -> dict[str, Any]:
    connection = _connect()
    try:
        return _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
    finally:
        connection.close()


def create_attendance_record(
    academy_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _normalized_values(values)
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        student = _get_student_row(
            connection,
            academy_id,
            data["student_id"],
        )
        student_pass = _get_student_pass_row(
            connection,
            academy_id,
            data["student_id"],
            data["student_pass_id"],
        )
        if student_pass["remaining_sessions"] <= 0:
            raise _error(
                409,
                "INSUFFICIENT_REMAINING_SESSIONS",
                "남은 수강 횟수가 없습니다.",
                student_pass_id=student_pass["id"],
                remaining_sessions=student_pass["remaining_sessions"],
            )
        if student_pass["expire_date"] < data["scheduled_at"][:10]:
            raise _error(
                400,
                "PASS_EXPIRED",
                "수업 예정일에 만료된 수강권입니다.",
                student_pass_id=student_pass["id"],
                expire_date=student_pass["expire_date"],
            )
        # 종료 시각은 클라이언트가 보내지 않고 수강권 스냅샷 시간으로 계산한다.
        # 이번 단계에서는 다른 예약과의 시간 겹침을 검사하지 않는다.
        scheduled_end_at = _add_minutes(
            data["scheduled_at"],
            student_pass["session_duration_minutes_snapshot"],
        )
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO attendance_records (
                    academy_id,
                    student_id,
                    student_pass_id,
                    pass_type_id_snapshot,
                    pass_type_name_snapshot,
                    student_name_snapshot,
                    class_name,
                    scheduled_at,
                    scheduled_end_at,
                    status,
                    session_delta,
                    memo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RESERVED', 0, ?)
                """,
                (
                    academy_id,
                    student["id"],
                    student_pass["id"],
                    student_pass["pass_type_id_snapshot"],
                    student_pass["pass_type_name_snapshot"],
                    student["name"],
                    data["class_name"],
                    data["scheduled_at"],
                    scheduled_end_at,
                    data.get("memo"),
                ),
            )
        return _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                cursor.lastrowid,
            )
        )
    finally:
        connection.close()


def update_attendance_record(
    academy_id: int,
    attendance_record_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    data = _require_update(
        values,
        {"class_name", "scheduled_at", "memo"},
    )
    connection = _connect()
    try:
        attendance = _get_attendance_row(
            connection,
            academy_id,
            attendance_record_id,
        )
        if attendance["status"] != "RESERVED":
            raise _error(
                409,
                "INVALID_ATTENDANCE_TRANSITION",
                "예약 상태의 수강 기록만 수정할 수 있습니다.",
                attendance_record_id=attendance_record_id,
                status=attendance["status"],
            )
        if "scheduled_at" in data:
            student_pass_id = attendance["student_pass_id"]
            student_id = attendance["student_id"]
            if student_pass_id is None or student_id is None:
                raise _error(
                    409,
                    "STUDENT_PASS_NOT_FOUND",
                    "연결된 보유 수강권이 없습니다.",
                    attendance_record_id=attendance_record_id,
                )
            student_pass = _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                student_pass_id,
            )
            if student_pass["expire_date"] < data["scheduled_at"][:10]:
                raise _error(
                    400,
                    "PASS_EXPIRED",
                    "변경한 수업일에 만료된 수강권입니다.",
                    student_pass_id=student_pass_id,
                    expire_date=student_pass["expire_date"],
                )
            # 시작 시각이 바뀌면 종료 시각도 서버가 다시 계산한다.
            data["scheduled_end_at"] = _add_minutes(
                data["scheduled_at"],
                student_pass["session_duration_minutes_snapshot"],
            )
        assignments = ", ".join(f"{field} = ?" for field in data)
        with connection:
            connection.execute(
                f"""
                UPDATE attendance_records
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND academy_id = ?
                """,
                (*data.values(), attendance_record_id, academy_id),
            )
        return _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
    finally:
        connection.close()


def complete_attendance(
    academy_id: int,
    attendance_record_id: int,
    completed_at: str | None,
) -> dict[str, Any]:
    """사업자가 수강을 완료 처리한다(RESERVED·CHECKED_IN 모두 허용).

    회원이 체크인한 기록이면 기존 `checked_in_at` 을 유지하고, 예약 상태에서
    바로 완료하면 완료 시각을 체크인 시각으로도 기록한다. 스키마가 COMPLETED
    에 두 시각을 모두 요구하기 때문이다.
    """
    completion_time = completed_at or _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            attendance = _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
            if attendance["status"] == "COMPLETED":
                raise _error(
                    409,
                    "ATTENDANCE_ALREADY_COMPLETED",
                    "이미 완료된 수강 기록입니다.",
                    attendance_record_id=attendance_record_id,
                )
            if attendance["status"] == "CANCELLED":
                raise _error(
                    409,
                    "ATTENDANCE_ALREADY_CANCELLED",
                    "취소된 수강 기록은 완료할 수 없습니다.",
                    attendance_record_id=attendance_record_id,
                )
            student_pass_id = attendance["student_pass_id"]
            student_id = attendance["student_id"]
            if student_pass_id is None or student_id is None:
                raise _error(
                    409,
                    "STUDENT_PASS_NOT_FOUND",
                    "연결된 보유 수강권이 없습니다.",
                    attendance_record_id=attendance_record_id,
                )
            student_pass = _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                student_pass_id,
            )
            if student_pass["remaining_sessions"] <= 0:
                raise _error(
                    409,
                    "INSUFFICIENT_REMAINING_SESSIONS",
                    "남은 수강 횟수가 없습니다.",
                    student_pass_id=student_pass_id,
                    remaining_sessions=0,
                )
            if (
                student_pass["expire_date"]
                < attendance["scheduled_at"][:10]
            ):
                raise _error(
                    400,
                    "PASS_EXPIRED",
                    "수업 예정일에 만료된 수강권입니다.",
                    student_pass_id=student_pass_id,
                    expire_date=student_pass["expire_date"],
                )
            cursor = connection.execute(
                """
                UPDATE student_passes
                SET remaining_sessions = remaining_sessions - 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND remaining_sessions > 0
                """,
                (student_pass_id,),
            )
            if cursor.rowcount != 1:
                raise _error(
                    409,
                    "INSUFFICIENT_REMAINING_SESSIONS",
                    "남은 수강 횟수가 없습니다.",
                    student_pass_id=student_pass_id,
                )
            connection.execute(
                """
                UPDATE attendance_records
                SET status = 'COMPLETED',
                    session_delta = -1,
                    checked_in_at = COALESCE(checked_in_at, ?),
                    checked_out_at = ?,
                    completed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('RESERVED', 'CHECKED_IN')
                """,
                (
                    completion_time,
                    completion_time,
                    completion_time,
                    attendance_record_id,
                ),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        return _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
    finally:
        connection.close()


def cancel_attendance(
    academy_id: int,
    attendance_record_id: int,
    *,
    cancelled_at: str | None,
    memo: str | None,
) -> dict[str, Any]:
    connection = _connect()
    try:
        attendance = _get_attendance_row(
            connection,
            academy_id,
            attendance_record_id,
        )
        if attendance["status"] == "CANCELLED":
            raise _error(
                409,
                "ATTENDANCE_ALREADY_CANCELLED",
                "이미 취소된 수강 기록입니다.",
                attendance_record_id=attendance_record_id,
            )
        if attendance["status"] == "COMPLETED":
            raise _error(
                409,
                "INVALID_ATTENDANCE_TRANSITION",
                "완료된 수강은 복구 API로 취소해야 합니다.",
                attendance_record_id=attendance_record_id,
            )
        # 체크인한 뒤에는 회원이 스스로 취소할 수 없다. 사업자 문의로 안내한다.
        if attendance["status"] == "CHECKED_IN":
            raise _error(
                409,
                "ATTENDANCE_ALREADY_CHECKED_IN",
                "이미 출석 처리된 예약은 취소할 수 없습니다. 아카데미에 문의해 주세요.",
                attendance_record_id=attendance_record_id,
            )
        with connection:
            connection.execute(
                """
                UPDATE attendance_records
                SET status = 'CANCELLED',
                    session_delta = 0,
                    cancelled_at = ?,
                    memo = COALESCE(?, memo),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND academy_id = ?
                """,
                (
                    cancelled_at or _now(),
                    memo,
                    attendance_record_id,
                    academy_id,
                ),
            )
        return _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
    finally:
        connection.close()


def restore_attendance(
    academy_id: int,
    attendance_record_id: int,
    *,
    reason: str,
    cancelled_at: str | None,
) -> dict[str, Any]:
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            attendance = _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
            if attendance["status"] == "CANCELLED":
                raise _error(
                    409,
                    "ATTENDANCE_ALREADY_CANCELLED",
                    "이미 취소된 수강 기록입니다.",
                    attendance_record_id=attendance_record_id,
                )
            if attendance["status"] != "COMPLETED":
                raise _error(
                    409,
                    "INVALID_ATTENDANCE_TRANSITION",
                    "완료된 수강 기록만 복구할 수 있습니다.",
                    attendance_record_id=attendance_record_id,
                )
            student_pass_id = attendance["student_pass_id"]
            student_id = attendance["student_id"]
            if student_pass_id is None or student_id is None:
                raise _error(
                    409,
                    "STUDENT_PASS_NOT_FOUND",
                    "연결된 보유 수강권이 없습니다.",
                    attendance_record_id=attendance_record_id,
                )
            student_pass = _get_student_pass_row(
                connection,
                academy_id,
                student_id,
                student_pass_id,
            )
            if (
                student_pass["remaining_sessions"] + 1
                > student_pass["total_sessions"]
            ):
                raise _error(
                    409,
                    "INVALID_REMAINING_SESSIONS_RESTORE",
                    "복구 후 잔여 횟수가 전체 횟수를 초과합니다.",
                    student_pass_id=student_pass_id,
                )
            connection.execute(
                """
                UPDATE student_passes
                SET remaining_sessions = remaining_sessions + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (student_pass_id,),
            )
            # 복구 후에는 CANCELLED 상태이므로 체크인·퇴실·완료 시각을 모두 비운다.
            connection.execute(
                """
                UPDATE attendance_records
                SET status = 'CANCELLED',
                    session_delta = 0,
                    checked_in_at = NULL,
                    checked_out_at = NULL,
                    completed_at = NULL,
                    cancelled_at = ?,
                    memo = CASE
                        WHEN memo IS NULL OR memo = ''
                        THEN ?
                        ELSE memo || char(10) || ?
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    cancelled_at or _now(),
                    f"복구 사유: {reason}",
                    f"복구 사유: {reason}",
                    attendance_record_id,
                ),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        return _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
    finally:
        connection.close()


def _require_attendance_pass(
    connection: sqlite3.Connection,
    academy_id: int,
    attendance: sqlite3.Row,
) -> sqlite3.Row:
    """수강 기록에 연결된 보유 수강권을 가져온다."""
    student_pass_id = attendance["student_pass_id"]
    student_id = attendance["student_id"]
    if student_pass_id is None or student_id is None:
        raise _error(
            409,
            "STUDENT_PASS_NOT_FOUND",
            "연결된 보유 수강권이 없습니다.",
            attendance_record_id=attendance["id"],
        )
    return _get_student_pass_row(
        connection,
        academy_id,
        student_id,
        student_pass_id,
    )


def check_in_attendance(
    academy_id: int,
    attendance_record_id: int,
) -> dict[str, Any]:
    """회원 출석 체크인. 잔여 횟수는 차감하지 않는다.

    이번 단계에서는 체크인 가능 시간 범위를 제한하지 않는다. 예약이
    RESERVED 이면 예정일 이전이나 이후에도 체크인할 수 있다.
    """
    checked_in_at = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            attendance = _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
            if attendance["status"] == "CHECKED_IN":
                raise _error(
                    409,
                    "ATTENDANCE_ALREADY_CHECKED_IN",
                    "이미 출석 처리된 예약입니다.",
                    attendance_record_id=attendance_record_id,
                    checked_in_at=attendance["checked_in_at"],
                )
            if attendance["status"] != "RESERVED":
                raise _error(
                    409,
                    "ATTENDANCE_NOT_RESERVED",
                    "예약 상태의 수강 기록만 출석할 수 있습니다.",
                    attendance_record_id=attendance_record_id,
                    status=attendance["status"],
                )
            student_pass = _require_attendance_pass(
                connection,
                academy_id,
                attendance,
            )
            if student_pass["remaining_sessions"] <= 0:
                raise _error(
                    409,
                    "INSUFFICIENT_REMAINING_SESSIONS",
                    "남은 수강 횟수가 없습니다.",
                    student_pass_id=student_pass["id"],
                    remaining_sessions=student_pass["remaining_sessions"],
                )
            if student_pass["expire_date"] < _today():
                raise _error(
                    400,
                    "PASS_EXPIRED",
                    "만료된 수강권입니다.",
                    student_pass_id=student_pass["id"],
                    expire_date=student_pass["expire_date"],
                )
            cursor = connection.execute(
                """
                UPDATE attendance_records
                SET status = 'CHECKED_IN',
                    session_delta = 0,
                    checked_in_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'RESERVED'
                """,
                (checked_in_at, attendance_record_id),
            )
            if cursor.rowcount != 1:
                raise _error(
                    409,
                    "ATTENDANCE_NOT_RESERVED",
                    "예약 상태의 수강 기록만 출석할 수 있습니다.",
                    attendance_record_id=attendance_record_id,
                )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        result = _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
        # 체크인 시점에는 차감하지 않으므로 잔여 횟수는 그대로다.
        result["remaining_sessions"] = student_pass["remaining_sessions"]
        return result
    finally:
        connection.close()


def check_out_attendance(
    academy_id: int,
    attendance_record_id: int,
) -> dict[str, Any]:
    """회원 퇴실. 수강을 완료 처리하고 잔여 횟수를 1회 차감한다.

    상태 변경과 차감을 한 트랜잭션에서 처리하고, 두 UPDATE 모두 조건부라
    중복 요청이 두 번 차감되지 않는다.
    """
    checked_out_at = _now()
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            attendance = _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
            if attendance["status"] == "COMPLETED":
                raise _error(
                    409,
                    "ATTENDANCE_ALREADY_COMPLETED",
                    "이미 완료된 수강 기록입니다.",
                    attendance_record_id=attendance_record_id,
                )
            if attendance["status"] != "CHECKED_IN":
                raise _error(
                    409,
                    "ATTENDANCE_NOT_CHECKED_IN",
                    "출석(체크인)한 수강만 퇴실할 수 있습니다.",
                    attendance_record_id=attendance_record_id,
                    status=attendance["status"],
                )
            student_pass = _require_attendance_pass(
                connection,
                academy_id,
                attendance,
            )
            if student_pass["remaining_sessions"] <= 0:
                raise _error(
                    409,
                    "INSUFFICIENT_REMAINING_SESSIONS",
                    "남은 수강 횟수가 없습니다.",
                    student_pass_id=student_pass["id"],
                    remaining_sessions=0,
                )
            deducted = connection.execute(
                """
                UPDATE student_passes
                SET remaining_sessions = remaining_sessions - 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND remaining_sessions > 0
                """,
                (student_pass["id"],),
            )
            if deducted.rowcount != 1:
                raise _error(
                    409,
                    "INSUFFICIENT_REMAINING_SESSIONS",
                    "남은 수강 횟수가 없습니다.",
                    student_pass_id=student_pass["id"],
                )
            updated = connection.execute(
                """
                UPDATE attendance_records
                SET status = 'COMPLETED',
                    session_delta = -1,
                    checked_out_at = ?,
                    completed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'CHECKED_IN'
                """,
                (checked_out_at, checked_out_at, attendance_record_id),
            )
            if updated.rowcount != 1:
                # 기록을 바꾸지 못하면 차감도 되돌린다.
                raise _error(
                    409,
                    "ATTENDANCE_NOT_CHECKED_IN",
                    "출석(체크인)한 수강만 퇴실할 수 있습니다.",
                    attendance_record_id=attendance_record_id,
                )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        result = _attendance_response(
            _get_attendance_row(
                connection,
                academy_id,
                attendance_record_id,
            )
        )
        result["remaining_sessions"] = (
            student_pass["remaining_sessions"] - 1
        )
        return result
    finally:
        connection.close()


# =========================================================
# 회원 포털 (조회 전용 요약과 예약 목록)
# =========================================================

RESERVATION_SORT_FIELDS = {
    "scheduled_at": "ar.scheduled_at",
    "id": "ar.id",
    "status": "ar.status",
    "class_name": "ar.class_name",
    "created_at": "ar.created_at",
}

_RESERVATION_COLUMNS = """
    ar.id AS id,
    ar.student_id AS student_id,
    ar.student_pass_id AS student_pass_id,
    ar.class_name AS class_name,
    ar.scheduled_at AS scheduled_at,
    ar.scheduled_end_at AS scheduled_end_at,
    ar.status AS status,
    ar.checked_in_at AS checked_in_at,
    ar.checked_out_at AS checked_out_at,
    ar.cancelled_at AS cancelled_at,
    ar.completed_at AS completed_at,
    ar.memo AS memo,
    ar.pass_type_id_snapshot AS pass_type_id_snapshot,
    ar.pass_type_name_snapshot AS pass_type_name,
    sp.remaining_sessions AS remaining_sessions,
    sp.expire_date AS pass_expire_date
"""


def _reservation_brief(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "class_name": row["class_name"],
        "scheduled_at": row["scheduled_at"],
        "scheduled_end_at": row["scheduled_end_at"],
        "status": row["status"],
    }


def get_student_portal_summary(
    academy_id: int,
    student_id: int,
) -> dict[str, Any]:
    """회원 포털 홈에 필요한 값을 한 번에 조회한다."""
    today = _today()
    now = _now()
    connection = _connect()
    try:
        student = _get_student_row(connection, academy_id, student_id)
        passes = connection.execute(
            """
            SELECT
                COUNT(*) AS total_count,
                COALESCE(SUM(CASE
                    WHEN remaining_sessions > 0 AND expire_date >= ?
                    THEN 1 ELSE 0
                END), 0) AS available_count,
                COALESCE(SUM(remaining_sessions), 0)
                    AS total_remaining_sessions,
                MIN(CASE
                    WHEN remaining_sessions > 0 AND expire_date >= ?
                    THEN expire_date
                END) AS nearest_expire_date
            FROM student_passes
            WHERE student_id = ?
            """,
            (today, today, student_id),
        ).fetchone()
        today_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM attendance_records
            WHERE student_id = ?
              AND academy_id = ?
              AND substr(scheduled_at, 1, 10) = ?
              AND status != 'CANCELLED'
            """,
            (student_id, academy_id, today),
        ).fetchone()[0]
        next_reservation = connection.execute(
            """
            SELECT id, class_name, scheduled_at, scheduled_end_at, status
            FROM attendance_records
            WHERE student_id = ?
              AND academy_id = ?
              AND status = 'RESERVED'
              AND scheduled_end_at >= ?
            ORDER BY scheduled_at ASC
            LIMIT 1
            """,
            (student_id, academy_id, now),
        ).fetchone()
        checked_in = connection.execute(
            """
            SELECT id, class_name, scheduled_at, scheduled_end_at, status
            FROM attendance_records
            WHERE student_id = ?
              AND academy_id = ?
              AND status = 'CHECKED_IN'
            ORDER BY checked_in_at DESC
            LIMIT 1
            """,
            (student_id, academy_id),
        ).fetchone()
        recent_rows = connection.execute(
            """
            SELECT id, class_name, scheduled_at, scheduled_end_at, status
            FROM attendance_records
            WHERE student_id = ? AND academy_id = ?
            ORDER BY scheduled_at DESC
            LIMIT 5
            """,
            (student_id, academy_id),
        ).fetchall()
        inquiries = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END), 0)
                    AS open_count,
                COALESCE(SUM(CASE
                    WHEN status = 'ANSWERED' THEN 1 ELSE 0
                END), 0) AS answered_count,
                COALESCE(SUM(CASE
                    WHEN status = 'CLOSED' THEN 1 ELSE 0
                END), 0) AS closed_count
            FROM inquiries
            WHERE student_id = ? AND academy_id = ?
            """,
            (student_id, academy_id),
        ).fetchone()
        return {
            "student": {
                "id": student["id"],
                "name": student["name"],
                "expire_date": student["expire_date"],
                "is_active": bool(
                    student["expire_date"] is not None
                    and student["expire_date"] >= today
                ),
            },
            "passes": {
                "total_count": passes["total_count"],
                "available_count": passes["available_count"],
                "total_remaining_sessions": passes[
                    "total_remaining_sessions"
                ],
                "nearest_expire_date": passes["nearest_expire_date"],
            },
            "attendance": {
                "today_count": today_count,
                "next_reservation": _reservation_brief(next_reservation),
                "currently_checked_in": _reservation_brief(checked_in),
                "recent_items": [
                    _reservation_brief(row) for row in recent_rows
                ],
            },
            "inquiries": {
                "open_count": inquiries["open_count"],
                "answered_count": inquiries["answered_count"],
                "closed_count": inquiries["closed_count"],
            },
        }
    finally:
        connection.close()


def list_student_reservations(
    academy_id: int,
    student_id: int,
    *,
    status: str | None,
    scheduled_from: str | None,
    scheduled_to: str | None,
    upcoming_only: bool,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """회원 예약 목록. 수강권 잔여 횟수까지 한 번에 돌려준다."""
    ordering = _sort_clause(sort, order, RESERVATION_SORT_FIELDS)
    conditions = ["ar.academy_id = ?", "ar.student_id = ?"]
    parameters: list[Any] = [academy_id, student_id]
    if status:
        conditions.append("ar.status = ?")
        parameters.append(status)
    if scheduled_from:
        conditions.append("ar.scheduled_at >= ?")
        parameters.append(scheduled_from)
    if scheduled_to:
        conditions.append("ar.scheduled_at <= ?")
        parameters.append(scheduled_to)
    if upcoming_only:
        # 아직 처리되지 않은 기록만 본다. 체크인한 수강은 예정 시각이
        # 지났어도 퇴실이 남아 있으므로 항상 포함한다.
        conditions.append("ar.status IN ('RESERVED', 'CHECKED_IN')")
        conditions.append(
            "(ar.status = 'CHECKED_IN' OR ar.scheduled_end_at >= ?)"
        )
        parameters.append(_now())
    where = f" WHERE {' AND '.join(conditions)}"
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        return _page(
            connection,
            f"""
            SELECT {_RESERVATION_COLUMNS}
            FROM attendance_records AS ar
            LEFT JOIN student_passes AS sp ON sp.id = ar.student_pass_id
            {where}
            ORDER BY {ordering}
            """,
            f"SELECT COUNT(*) FROM attendance_records AS ar{where}",
            parameters,
            limit,
            offset,
        )
    finally:
        connection.close()


# =========================================================
# 문의(1:1 문의와 답변)
# =========================================================

INQUIRY_CATEGORIES = (
    "PASS",
    "RESERVATION",
    "ATTENDANCE",
    "CHECK_IN_OUT",
    "DEDUCTION_ERROR",
    "EXTENSION",
    "REFUND",
    "FACILITY",
    "OTHER",
)

INQUIRY_SORT_FIELDS = {
    "created_at": "i.created_at",
    "updated_at": "i.updated_at",
    "id": "i.id",
    "status": "i.status",
    "category": "i.category",
}

_INQUIRY_COLUMNS = """
    i.id AS id,
    i.academy_id AS academy_id,
    i.student_id AS student_id,
    i.student_name_snapshot AS student_name_snapshot,
    i.category AS category,
    i.title AS title,
    i.status AS status,
    i.related_student_pass_id AS related_student_pass_id,
    i.related_attendance_record_id AS related_attendance_record_id,
    i.created_at AS created_at,
    i.updated_at AS updated_at,
    i.closed_at AS closed_at,
    (
        SELECT COUNT(*)
        FROM inquiry_messages AS m
        WHERE m.inquiry_id = i.id
    ) AS message_count,
    (
        SELECT MAX(m.created_at)
        FROM inquiry_messages AS m
        WHERE m.inquiry_id = i.id
    ) AS last_message_at
"""


def _get_inquiry_row(
    connection: sqlite3.Connection,
    academy_id: int,
    inquiry_id: int,
    student_id: int | None = None,
) -> sqlite3.Row:
    conditions = ["i.id = ?", "i.academy_id = ?"]
    parameters: list[Any] = [inquiry_id, academy_id]
    if student_id is not None:
        conditions.append("i.student_id = ?")
        parameters.append(student_id)
    row = connection.execute(
        f"""
        SELECT {_INQUIRY_COLUMNS}
        FROM inquiries AS i
        WHERE {' AND '.join(conditions)}
        """,
        parameters,
    ).fetchone()
    if row is None:
        raise _error(
            404,
            "INQUIRY_NOT_FOUND",
            "문의를 찾을 수 없습니다.",
            academy_id=academy_id,
            inquiry_id=inquiry_id,
        )
    return row


def _inquiry_messages(
    connection: sqlite3.Connection,
    inquiry_id: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, inquiry_id, sender_type, message, created_at
        FROM inquiry_messages
        WHERE inquiry_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (inquiry_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _inquiry_detail(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
) -> dict[str, Any]:
    detail = dict(row)
    related_pass = None
    if row["related_student_pass_id"] is not None:
        pass_row = connection.execute(
            """
            SELECT id, pass_type_name_snapshot, remaining_sessions,
                   total_sessions, expire_date
            FROM student_passes
            WHERE id = ?
            """,
            (row["related_student_pass_id"],),
        ).fetchone()
        if pass_row is not None:
            related_pass = {
                "id": pass_row["id"],
                "pass_type_name": pass_row["pass_type_name_snapshot"],
                "total_sessions": pass_row["total_sessions"],
                "remaining_sessions": pass_row["remaining_sessions"],
                "expire_date": pass_row["expire_date"],
            }
    related_record = None
    if row["related_attendance_record_id"] is not None:
        record_row = connection.execute(
            """
            SELECT id, class_name, scheduled_at, scheduled_end_at, status
            FROM attendance_records
            WHERE id = ?
            """,
            (row["related_attendance_record_id"],),
        ).fetchone()
        if record_row is not None:
            related_record = _reservation_brief(record_row)
    detail["related_student_pass"] = related_pass
    detail["related_attendance_record"] = related_record
    detail["messages"] = _inquiry_messages(connection, row["id"])
    return detail


def _clean_message(message: Any) -> str:
    text = str(message or "").strip()
    if not text:
        raise _error(
            400,
            "EMPTY_INQUIRY_MESSAGE",
            "메시지 내용을 입력해 주세요.",
        )
    return text


def create_inquiry(
    academy_id: int,
    student_id: int,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    """문의와 최초 메시지를 한 트랜잭션으로 생성한다."""
    data = _normalized_values(values)
    category = data.get("category")
    if category not in INQUIRY_CATEGORIES:
        raise _error(
            422,
            "INVALID_INQUIRY_CATEGORY",
            "허용되지 않은 문의 유형입니다.",
            category=category,
        )
    title = str(data.get("title") or "").strip()
    if not title:
        raise _error(400, "EMPTY_INQUIRY_TITLE", "제목을 입력해 주세요.")
    message = _clean_message(data.get("message"))
    related_pass_id = data.get("related_student_pass_id")
    related_record_id = data.get("related_attendance_record_id")

    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            student = _get_student_row(connection, academy_id, student_id)
            if related_pass_id is not None:
                owned = connection.execute(
                    """
                    SELECT 1 FROM student_passes
                    WHERE id = ? AND student_id = ?
                    """,
                    (related_pass_id, student_id),
                ).fetchone()
                if owned is None:
                    raise _error(
                        400,
                        "STUDENT_PASS_OWNER_MISMATCH",
                        "본인 수강권만 문의에 연결할 수 있습니다.",
                        student_pass_id=related_pass_id,
                    )
            if related_record_id is not None:
                owned = connection.execute(
                    """
                    SELECT 1 FROM attendance_records
                    WHERE id = ? AND student_id = ? AND academy_id = ?
                    """,
                    (related_record_id, student_id, academy_id),
                ).fetchone()
                if owned is None:
                    raise _error(
                        400,
                        "ATTENDANCE_RECORD_OWNER_MISMATCH",
                        "본인 수강 기록만 문의에 연결할 수 있습니다.",
                        attendance_record_id=related_record_id,
                    )
            cursor = connection.execute(
                """
                INSERT INTO inquiries (
                    academy_id,
                    student_id,
                    student_name_snapshot,
                    category,
                    title,
                    status,
                    related_student_pass_id,
                    related_attendance_record_id
                ) VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?)
                """,
                (
                    academy_id,
                    student_id,
                    student["name"],
                    category,
                    title,
                    related_pass_id,
                    related_record_id,
                ),
            )
            inquiry_id = cursor.lastrowid
            connection.execute(
                """
                INSERT INTO inquiry_messages (
                    inquiry_id, sender_type, message
                ) VALUES (?, 'STUDENT', ?)
                """,
                (inquiry_id, message),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        return _inquiry_detail(
            connection,
            _get_inquiry_row(connection, academy_id, inquiry_id, student_id),
        )
    finally:
        connection.close()


def _list_inquiries(
    academy_id: int,
    *,
    student_id: int | None,
    status: str | None,
    category: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
    verify_student: bool,
) -> dict[str, Any]:
    ordering = _sort_clause(sort, order, INQUIRY_SORT_FIELDS)
    conditions = ["i.academy_id = ?"]
    parameters: list[Any] = [academy_id]
    if student_id is not None:
        conditions.append("i.student_id = ?")
        parameters.append(student_id)
    if status:
        conditions.append("i.status = ?")
        parameters.append(status)
    if category:
        conditions.append("i.category = ?")
        parameters.append(category)
    where = f" WHERE {' AND '.join(conditions)}"
    connection = _connect()
    try:
        if verify_student and student_id is not None:
            _get_student_row(connection, academy_id, student_id)
        else:
            _get_academy_row(connection, academy_id)
        return _page(
            connection,
            f"""
            SELECT {_INQUIRY_COLUMNS}
            FROM inquiries AS i
            {where}
            ORDER BY {ordering}
            """,
            f"SELECT COUNT(*) FROM inquiries AS i{where}",
            parameters,
            limit,
            offset,
        )
    finally:
        connection.close()


def list_student_inquiries(
    academy_id: int,
    student_id: int,
    *,
    status: str | None,
    category: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    return _list_inquiries(
        academy_id,
        student_id=student_id,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        verify_student=True,
    )


def list_academy_inquiries(
    academy_id: int,
    *,
    student_id: int | None,
    status: str | None,
    category: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    return _list_inquiries(
        academy_id,
        student_id=student_id,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
        verify_student=False,
    )


def get_student_inquiry(
    academy_id: int,
    student_id: int,
    inquiry_id: int,
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_student_row(connection, academy_id, student_id)
        return _inquiry_detail(
            connection,
            _get_inquiry_row(connection, academy_id, inquiry_id, student_id),
        )
    finally:
        connection.close()


def get_academy_inquiry(
    academy_id: int,
    inquiry_id: int,
) -> dict[str, Any]:
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        return _inquiry_detail(
            connection,
            _get_inquiry_row(connection, academy_id, inquiry_id),
        )
    finally:
        connection.close()


def _add_inquiry_message(
    academy_id: int,
    inquiry_id: int,
    *,
    student_id: int | None,
    sender_type: str,
    message: Any,
    next_status: str,
) -> dict[str, Any]:
    """문의에 메시지를 추가하고 상태를 갱신한다(한 트랜잭션)."""
    text = _clean_message(message)
    connection = _connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            if student_id is not None:
                _get_student_row(connection, academy_id, student_id)
            inquiry = _get_inquiry_row(
                connection,
                academy_id,
                inquiry_id,
                student_id,
            )
            if inquiry["status"] == "CLOSED":
                raise _error(
                    409,
                    "INQUIRY_CLOSED",
                    "종료된 문의에는 메시지를 추가할 수 없습니다.",
                    inquiry_id=inquiry_id,
                )
            connection.execute(
                """
                INSERT INTO inquiry_messages (
                    inquiry_id, sender_type, message
                ) VALUES (?, ?, ?)
                """,
                (inquiry_id, sender_type, text),
            )
            connection.execute(
                """
                UPDATE inquiries
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (next_status, inquiry_id),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        return _inquiry_detail(
            connection,
            _get_inquiry_row(connection, academy_id, inquiry_id, student_id),
        )
    finally:
        connection.close()


def add_student_inquiry_message(
    academy_id: int,
    student_id: int,
    inquiry_id: int,
    message: Any,
) -> dict[str, Any]:
    """회원이 메시지를 추가하면 답변 대기(OPEN) 상태로 되돌린다."""
    return _add_inquiry_message(
        academy_id,
        inquiry_id,
        student_id=student_id,
        sender_type="STUDENT",
        message=message,
        next_status="OPEN",
    )


def add_academy_inquiry_message(
    academy_id: int,
    inquiry_id: int,
    message: Any,
) -> dict[str, Any]:
    """아카데미가 답변하면 상태를 ANSWERED 로 바꾼다."""
    return _add_inquiry_message(
        academy_id,
        inquiry_id,
        student_id=None,
        sender_type="ACADEMY",
        message=message,
        next_status="ANSWERED",
    )


def _close_inquiry(
    academy_id: int,
    inquiry_id: int,
    student_id: int | None,
) -> dict[str, Any]:
    connection = _connect()
    try:
        if student_id is not None:
            _get_student_row(connection, academy_id, student_id)
        _get_inquiry_row(connection, academy_id, inquiry_id, student_id)
        with connection:
            connection.execute(
                """
                UPDATE inquiries
                SET status = 'CLOSED',
                    closed_at = COALESCE(closed_at, ?),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (_now(), inquiry_id),
            )
        return _inquiry_detail(
            connection,
            _get_inquiry_row(connection, academy_id, inquiry_id, student_id),
        )
    finally:
        connection.close()


def close_student_inquiry(
    academy_id: int,
    student_id: int,
    inquiry_id: int,
) -> dict[str, Any]:
    return _close_inquiry(academy_id, inquiry_id, student_id)


def close_academy_inquiry(
    academy_id: int,
    inquiry_id: int,
) -> dict[str, Any]:
    return _close_inquiry(academy_id, inquiry_id, None)


# =========================================================
# 운영 분석 · 관리 목록 · 정합성 점검 (조회 전용)
# 화면과 향후 Agent Tool이 함께 사용하는 집계 함수 모음이다.
# 이 구역의 함수는 어떤 데이터도 변경하지 않는다.
# =========================================================

# 대시보드 KPI에서 사용하는 고정 기준값.
DASHBOARD_EXPIRING_DAYS = 14
DASHBOARD_LOW_BALANCE_MAX_REMAINING = 3

REREGISTRATION_REASONS = (
    "LOW_REMAINING_SESSIONS",
    "EXPIRING_SOON",
    "ALL_PASSES_EXHAUSTED",
    "EXPIRED_WITH_RECENT_ATTENDANCE",
)

PASS_TYPE_ANALYTICS_SORT_FIELDS = {
    "issued_count": "issued_count",
    "issued_sessions": "issued_sessions",
    "issued_price_total": "issued_price_total",
    "remaining_sessions": "remaining_sessions",
    "used_sessions": "used_sessions",
    "completed_attendance_count": "completed_attendance_count",
    "pass_type_name": "pass_type_name_snapshot",
    "pass_type_id": "pass_type_id_snapshot",
}

PENDING_ATTENDANCE_SORT_FIELDS = {
    "scheduled_at": "ar.scheduled_at",
    "id": "ar.id",
    "student_name": "ar.student_name_snapshot",
    "class_name": "ar.class_name",
}

EXPIRING_PASS_SORT_FIELDS = {
    "expire_date": "sp.expire_date",
    "remaining_sessions": "sp.remaining_sessions",
    "student_name": "s.name",
    "id": "sp.id",
}

LOW_BALANCE_PASS_SORT_FIELDS = {
    "remaining_sessions": "sp.remaining_sessions",
    "expire_date": "sp.expire_date",
    "student_name": "s.name",
    "id": "sp.id",
}

REREGISTRATION_SORT_FIELDS = {
    "nearest_expire_date": (
        "nearest_expire_date IS NULL, nearest_expire_date"
    ),
    "remaining_sessions": "remaining_sessions",
    "last_completed_at": "last_completed_at IS NULL, last_completed_at",
    "student_name": "student_name",
    "student_id": "student_id",
}


def _resolve_period(
    date_from: str | None,
    date_to: str | None,
) -> tuple[date, date]:
    """조회 기간을 확정한다. 기본값은 오늘을 포함한 최근 30일이다."""
    end = date.fromisoformat(date_to) if date_to else date.today()
    start = (
        date.fromisoformat(date_from)
        if date_from
        else end - timedelta(days=29)
    )
    if start > end:
        raise _error(
            400,
            "INVALID_DATE_RANGE",
            "조회 시작일이 종료일보다 늦습니다.",
            date_from=start.isoformat(),
            date_to=end.isoformat(),
        )
    return start, end


# students.created_at 등 DB 기본값(CURRENT_TIMESTAMP)은 UTC로 저장되는
# 반면, 만료일·구매일 등 애플리케이션이 기록하는 값과 _today()는 로컬
# 시각이다. 등록일 기준 집계는 로컬 날짜로 변환해 비교한다.
STUDENT_CREATED_LOCAL = "datetime(created_at, 'localtime')"


def _period_expression(column: str, group_by: str) -> str:
    """집계 단위별 기간 키 SQL 식을 만든다(허용값만 사용)."""
    date_part = f"substr({column}, 1, 10)"
    if group_by == "day":
        return date_part
    if group_by == "week":
        # 해당 주의 월요일. SQLite 'weekday 0'은 다음 일요일로 이동한다.
        return f"date({date_part}, 'weekday 0', '-6 days')"
    if group_by == "month":
        return f"date({date_part}, 'start of month')"
    raise _error(
        422,
        "INVALID_GROUP_BY",
        "집계 단위는 day, week, month 중 하나여야 합니다.",
        group_by=group_by,
    )


def _period_key(value: date, group_by: str) -> str:
    if group_by == "week":
        return (value - timedelta(days=value.weekday())).isoformat()
    if group_by == "month":
        return value.replace(day=1).isoformat()
    return value.isoformat()


def _period_keys(start: date, end: date, group_by: str) -> list[str]:
    """기간 전체의 키를 순서대로 만든다(데이터가 없는 구간도 포함)."""
    keys: list[str] = []
    seen: set[str] = set()
    current = start
    while current <= end:
        key = _period_key(current, group_by)
        if key not in seen:
            seen.add(key)
            keys.append(key)
        current += timedelta(days=1)
    return keys


def _change(current: int, previous: int) -> dict[str, Any]:
    """직전 기간 대비 증감. 직전 값이 0이면 비율은 null로 둔다."""
    return {
        "count": current - previous,
        "rate": (
            None
            if previous == 0
            else round((current - previous) / previous * 100, 2)
        ),
    }


def get_dashboard_analytics(
    academy_id: int,
    *,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    """운영 대시보드 KPI를 한 번에 조회한다."""
    start, end = _resolve_period(date_from, date_to)
    start_text = start.isoformat()
    end_text = end.isoformat()
    today = _today()
    now = _now()
    expiring_limit = (
        date.fromisoformat(today)
        + timedelta(days=DASHBOARD_EXPIRING_DAYS)
    ).isoformat()
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        students = connection.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE
                    WHEN expire_date IS NOT NULL AND expire_date >= ?
                    THEN 1 ELSE 0
                END), 0) AS active,
                COALESCE(SUM(CASE
                    WHEN substr({STUDENT_CREATED_LOCAL}, 1, 10)
                         BETWEEN ? AND ?
                    THEN 1 ELSE 0
                END), 0) AS new_in_period
            FROM students
            WHERE academy_id = ?
            """,
            (today, start_text, end_text, academy_id),
        ).fetchone()
        passes = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE
                    WHEN substr(sp.purchased_at, 1, 10) BETWEEN ? AND ?
                    THEN 1 ELSE 0
                END), 0) AS issued_in_period,
                COALESCE(SUM(CASE
                    WHEN sp.remaining_sessions > 0 AND sp.expire_date >= ?
                    THEN 1 ELSE 0
                END), 0) AS available,
                COALESCE(SUM(sp.remaining_sessions), 0)
                    AS total_remaining_sessions,
                COALESCE(SUM(CASE
                    WHEN sp.remaining_sessions > 0
                     AND sp.expire_date >= ?
                     AND sp.expire_date <= ?
                    THEN 1 ELSE 0
                END), 0) AS expiring_within_14_days,
                COALESCE(SUM(CASE
                    WHEN sp.expire_date >= ? AND sp.remaining_sessions <= ?
                    THEN 1 ELSE 0
                END), 0) AS low_balance_count
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            WHERE s.academy_id = ?
            """,
            (
                start_text,
                end_text,
                today,
                today,
                expiring_limit,
                today,
                DASHBOARD_LOW_BALANCE_MAX_REMAINING,
                academy_id,
            ),
        ).fetchone()
        attendance = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE
                    WHEN status = 'RESERVED'
                     AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
                    THEN 1 ELSE 0
                END), 0) AS reserved_in_period,
                COALESCE(SUM(CASE
                    WHEN status = 'COMPLETED'
                     AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
                    THEN 1 ELSE 0
                END), 0) AS completed_in_period,
                COALESCE(SUM(CASE
                    WHEN status = 'CANCELLED'
                     AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
                    THEN 1 ELSE 0
                END), 0) AS cancelled_in_period,
                COALESCE(SUM(CASE
                    WHEN status = 'RESERVED' AND scheduled_at < ?
                    THEN 1 ELSE 0
                END), 0) AS pending_past
            FROM attendance_records
            WHERE academy_id = ?
            """,
            (
                start_text,
                end_text,
                start_text,
                end_text,
                start_text,
                end_text,
                now,
                academy_id,
            ),
        ).fetchone()
        total_students = students["total"]
        active_students = students["active"]
        return {
            "period": {
                "date_from": start_text,
                "date_to": end_text,
            },
            "students": {
                "total": total_students,
                "active": active_students,
                "inactive": total_students - active_students,
                "new_in_period": students["new_in_period"],
            },
            "student_passes": {
                key: passes[key]
                for key in (
                    "issued_in_period",
                    "available",
                    "total_remaining_sessions",
                    "expiring_within_14_days",
                    "low_balance_count",
                )
            },
            "attendance": {
                key: attendance[key]
                for key in (
                    "reserved_in_period",
                    "completed_in_period",
                    "cancelled_in_period",
                    "pending_past",
                )
            },
        }
    finally:
        connection.close()


def get_registration_analytics(
    academy_id: int,
    *,
    date_from: str | None,
    date_to: str | None,
    group_by: str,
) -> dict[str, Any]:
    """신규 수강생과 수강권 발급 추이를 조회한다."""
    start, end = _resolve_period(date_from, date_to)
    length = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=length - 1)
    student_period = _period_expression(STUDENT_CREATED_LOCAL, group_by)
    pass_period = _period_expression("sp.purchased_at", group_by)
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)

        def count_students(period_start: date, period_end: date) -> int:
            return connection.execute(
                f"""
                SELECT COUNT(*)
                FROM students
                WHERE academy_id = ?
                  AND substr({STUDENT_CREATED_LOCAL}, 1, 10)
                      BETWEEN ? AND ?
                """,
                (
                    academy_id,
                    period_start.isoformat(),
                    period_end.isoformat(),
                ),
            ).fetchone()[0]

        def count_passes(period_start: date, period_end: date) -> int:
            return connection.execute(
                """
                SELECT COUNT(*)
                FROM student_passes AS sp
                JOIN students AS s ON s.id = sp.student_id
                WHERE s.academy_id = ?
                  AND substr(sp.purchased_at, 1, 10) BETWEEN ? AND ?
                """,
                (
                    academy_id,
                    period_start.isoformat(),
                    period_end.isoformat(),
                ),
            ).fetchone()[0]

        student_rows = connection.execute(
            f"""
            SELECT {student_period} AS period, COUNT(*) AS students
            FROM students
            WHERE academy_id = ?
              AND substr({STUDENT_CREATED_LOCAL}, 1, 10) BETWEEN ? AND ?
            GROUP BY period
            """,
            (academy_id, start.isoformat(), end.isoformat()),
        ).fetchall()
        pass_rows = connection.execute(
            f"""
            SELECT {pass_period} AS period, COUNT(*) AS student_passes
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            WHERE s.academy_id = ?
              AND substr(sp.purchased_at, 1, 10) BETWEEN ? AND ?
            GROUP BY period
            """,
            (academy_id, start.isoformat(), end.isoformat()),
        ).fetchall()

        student_counts = {row["period"]: row["students"] for row in student_rows}
        pass_counts = {
            row["period"]: row["student_passes"] for row in pass_rows
        }
        total_students = count_students(start, end)
        total_passes = count_passes(start, end)
        previous_students = count_students(previous_start, previous_end)
        previous_passes = count_passes(previous_start, previous_end)
        return {
            "period": {
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
            },
            "group_by": group_by,
            "total_students": total_students,
            "total_student_passes": total_passes,
            "previous_period": {
                "date_from": previous_start.isoformat(),
                "date_to": previous_end.isoformat(),
                "total_students": previous_students,
                "total_student_passes": previous_passes,
            },
            "student_change": _change(total_students, previous_students),
            "student_pass_change": _change(total_passes, previous_passes),
            "series": [
                {
                    "period": key,
                    "students": student_counts.get(key, 0),
                    "student_passes": pass_counts.get(key, 0),
                }
                for key in _period_keys(start, end, group_by)
            ],
        }
    finally:
        connection.close()


def get_attendance_analytics(
    academy_id: int,
    *,
    date_from: str | None,
    date_to: str | None,
    group_by: str,
) -> dict[str, Any]:
    """예약·완료·취소와 미처리 예약 추이를 조회한다."""
    start, end = _resolve_period(date_from, date_to)
    start_text = start.isoformat()
    end_text = end.isoformat()
    now = _now()
    period_expression = _period_expression("scheduled_at", group_by)
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        totals = connection.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN status = 'RESERVED' THEN 1 ELSE 0 END), 0)
                    AS reserved,
                COALESCE(SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), 0)
                    AS completed,
                COALESCE(SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END), 0)
                    AS cancelled,
                COALESCE(SUM(CASE
                    WHEN status = 'RESERVED' AND scheduled_at < ?
                    THEN 1 ELSE 0
                END), 0) AS pending_past
            FROM attendance_records
            WHERE academy_id = ?
              AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
            """,
            (now, academy_id, start_text, end_text),
        ).fetchone()
        series_rows = connection.execute(
            f"""
            SELECT
                {period_expression} AS period,
                COALESCE(SUM(CASE WHEN status = 'RESERVED' THEN 1 ELSE 0 END), 0)
                    AS reserved,
                COALESCE(SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END), 0)
                    AS completed,
                COALESCE(SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END), 0)
                    AS cancelled
            FROM attendance_records
            WHERE academy_id = ?
              AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
            GROUP BY period
            """,
            (academy_id, start_text, end_text),
        ).fetchall()
        by_class_name = connection.execute(
            """
            SELECT class_name, COUNT(*) AS completed
            FROM attendance_records
            WHERE academy_id = ?
              AND status = 'COMPLETED'
              AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
            GROUP BY class_name
            ORDER BY completed DESC, class_name ASC
            """,
            (academy_id, start_text, end_text),
        ).fetchall()
        by_pass_type = connection.execute(
            """
            SELECT
                pass_type_id_snapshot,
                MAX(pass_type_name_snapshot) AS pass_type_name_snapshot,
                COUNT(*) AS completed
            FROM attendance_records
            WHERE academy_id = ?
              AND status = 'COMPLETED'
              AND substr(scheduled_at, 1, 10) BETWEEN ? AND ?
            GROUP BY pass_type_id_snapshot
            ORDER BY completed DESC, pass_type_id_snapshot ASC
            """,
            (academy_id, start_text, end_text),
        ).fetchall()
        series_map = {row["period"]: row for row in series_rows}
        return {
            "period": {"date_from": start_text, "date_to": end_text},
            "group_by": group_by,
            "totals": {
                key: totals[key]
                for key in ("reserved", "completed", "cancelled", "pending_past")
            },
            "series": [
                {
                    "period": key,
                    "reserved": (
                        series_map[key]["reserved"] if key in series_map else 0
                    ),
                    "completed": (
                        series_map[key]["completed"] if key in series_map else 0
                    ),
                    "cancelled": (
                        series_map[key]["cancelled"] if key in series_map else 0
                    ),
                }
                for key in _period_keys(start, end, group_by)
            ],
            "by_class_name": [dict(row) for row in by_class_name],
            "by_pass_type": [dict(row) for row in by_pass_type],
        }
    finally:
        connection.close()


def get_pass_type_analytics(
    academy_id: int,
    *,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """기간 내 발급된 수강권을 종류 스냅샷 기준으로 집계한다."""
    start, end = _resolve_period(date_from, date_to)
    ordering = _sort_clause(sort, order, PASS_TYPE_ANALYTICS_SORT_FIELDS)
    parameters = (academy_id, start.isoformat(), end.isoformat())
    grouped_sql = """
        SELECT
            sp.pass_type_id_snapshot AS pass_type_id_snapshot,
            MAX(sp.pass_type_name_snapshot) AS pass_type_name_snapshot,
            COUNT(*) AS issued_count,
            COALESCE(SUM(sp.total_sessions), 0) AS issued_sessions,
            COALESCE(SUM(sp.remaining_sessions), 0) AS remaining_sessions,
            COALESCE(
                SUM(sp.total_sessions - sp.remaining_sessions), 0
            ) AS used_sessions,
            COALESCE(SUM(sp.price_snapshot), 0) AS issued_price_total,
            COALESCE(SUM((
                SELECT COUNT(*)
                FROM attendance_records AS ar
                WHERE ar.student_pass_id = sp.id
                  AND ar.status = 'COMPLETED'
            )), 0) AS completed_attendance_count
        FROM student_passes AS sp
        JOIN students AS s ON s.id = sp.student_id
        WHERE s.academy_id = ?
          AND substr(sp.purchased_at, 1, 10) BETWEEN ? AND ?
        GROUP BY sp.pass_type_id_snapshot
    """
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        rows = connection.execute(
            f"{grouped_sql} ORDER BY {ordering} LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        ).fetchall()
        total = connection.execute(
            f"SELECT COUNT(*) FROM ({grouped_sql})",
            parameters,
        ).fetchone()[0]
        return {
            "period": {
                "date_from": start.isoformat(),
                "date_to": end.isoformat(),
            },
            "items": [dict(row) for row in rows],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }
    finally:
        connection.close()


def list_pending_attendance(
    academy_id: int,
    *,
    scheduled_before: str | None,
    scheduled_from: str | None,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """예정 시각이 지났는데 아직 RESERVED 상태인 예약을 조회한다.

    현재 스키마에는 결석 상태가 없으므로 결석 확정이 아니라 '미처리
    예약'으로만 해석한다.
    """
    ordering = _sort_clause(sort, order, PENDING_ATTENDANCE_SORT_FIELDS)
    conditions = [
        "ar.academy_id = ?",
        "ar.status = 'RESERVED'",
        "ar.scheduled_at < ?",
    ]
    parameters: list[Any] = [academy_id, scheduled_before or _now()]
    if scheduled_from:
        conditions.append("ar.scheduled_at >= ?")
        parameters.append(scheduled_from)
    where = f" WHERE {' AND '.join(conditions)}"
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        return _page(
            connection,
            f"""
            SELECT
                ar.id AS attendance_record_id,
                ar.student_id AS student_id,
                ar.student_name_snapshot AS student_name,
                ar.student_pass_id AS student_pass_id,
                ar.pass_type_id_snapshot AS pass_type_id_snapshot,
                ar.pass_type_name_snapshot AS pass_type_name,
                ar.class_name AS class_name,
                ar.scheduled_at AS scheduled_at,
                ar.status AS status,
                sp.remaining_sessions AS remaining_sessions,
                sp.expire_date AS expire_date
            FROM attendance_records AS ar
            LEFT JOIN student_passes AS sp ON sp.id = ar.student_pass_id
            {where}
            ORDER BY {ordering}
            """,
            f"SELECT COUNT(*) FROM attendance_records AS ar{where}",
            parameters,
            limit,
            offset,
        )
    finally:
        connection.close()


def list_expiring_passes(
    academy_id: int,
    *,
    days: int,
    include_expired: bool,
    remaining_only: bool,
    expired_only: bool,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """지정한 일수 안에 만료되는 보유 수강권을 조회한다.

    `expired_only`가 참이면 이미 만료된 수강권만 조회한다. 잔여 횟수가
    남은 채로 만료된 수강권을 찾을 때 사용한다.
    """
    today = _today()
    limit_date = (
        date.fromisoformat(today) + timedelta(days=days)
    ).isoformat()
    ordering = _sort_clause(sort, order, EXPIRING_PASS_SORT_FIELDS)
    conditions = ["s.academy_id = ?", "sp.expire_date <= ?"]
    parameters: list[Any] = [academy_id, limit_date]
    if expired_only:
        conditions.append("sp.expire_date < ?")
        parameters.append(today)
    elif not include_expired:
        conditions.append("sp.expire_date >= ?")
        parameters.append(today)
    if remaining_only:
        conditions.append("sp.remaining_sessions > 0")
    where = f" WHERE {' AND '.join(conditions)}"
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        page = _page(
            connection,
            f"""
            SELECT
                sp.id AS student_pass_id,
                sp.student_id AS student_id,
                s.name AS student_name,
                s.phone AS student_phone,
                sp.pass_type_id_snapshot AS pass_type_id_snapshot,
                sp.pass_type_name_snapshot AS pass_type_name,
                sp.total_sessions AS total_sessions,
                sp.remaining_sessions AS remaining_sessions,
                sp.expire_date AS expire_date,
                (
                    SELECT MAX(ar.completed_at)
                    FROM attendance_records AS ar
                    WHERE ar.student_pass_id = sp.id
                      AND ar.status = 'COMPLETED'
                ) AS last_completed_at
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            {where}
            ORDER BY {ordering}
            """,
            f"""
            SELECT COUNT(*)
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            {where}
            """,
            parameters,
            limit,
            offset,
        )
        # 남은 일수는 SELECT 절 파라미터를 늘리지 않도록 여기서 계산한다.
        today_date = date.fromisoformat(today)
        page["items"] = [
            {
                **item,
                "days_left": (
                    date.fromisoformat(item["expire_date"]) - today_date
                ).days,
            }
            for item in page["items"]
        ]
        return page
    finally:
        connection.close()


def list_low_balance_passes(
    academy_id: int,
    *,
    max_remaining: int,
    available_only: bool,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """잔여 횟수가 기준 이하인 보유 수강권을 조회한다."""
    today = _today()
    ordering = _sort_clause(sort, order, LOW_BALANCE_PASS_SORT_FIELDS)
    conditions = ["s.academy_id = ?", "sp.remaining_sessions <= ?"]
    parameters: list[Any] = [academy_id, max_remaining]
    if available_only:
        conditions.append("sp.expire_date >= ?")
        parameters.append(today)
    where = f" WHERE {' AND '.join(conditions)}"
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        return _page(
            connection,
            f"""
            SELECT
                sp.id AS student_pass_id,
                sp.student_id AS student_id,
                s.name AS student_name,
                s.phone AS student_phone,
                sp.pass_type_id_snapshot AS pass_type_id_snapshot,
                sp.pass_type_name_snapshot AS pass_type_name,
                sp.total_sessions AS total_sessions,
                sp.remaining_sessions AS remaining_sessions,
                sp.expire_date AS expire_date,
                (
                    SELECT MAX(ar.completed_at)
                    FROM attendance_records AS ar
                    WHERE ar.student_pass_id = sp.id
                      AND ar.status = 'COMPLETED'
                ) AS last_completed_at
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            {where}
            ORDER BY {ordering}
            """,
            f"""
            SELECT COUNT(*)
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            {where}
            """,
            parameters,
            limit,
            offset,
        )
    finally:
        connection.close()


def _reregistration_reasons(
    row: sqlite3.Row,
    *,
    max_remaining: int,
    expiring_limit: str,
    recent_threshold: str,
) -> list[str]:
    """후보 사유 코드를 SQL 조건과 동일한 순서로 만든다."""
    reasons: list[str] = []
    if (
        row["available_count"] > 0
        and row["available_remaining_sessions"] <= max_remaining
    ):
        reasons.append("LOW_REMAINING_SESSIONS")
    if (
        row["available_count"] > 0
        and row["nearest_expire_date"] is not None
        and row["nearest_expire_date"] <= expiring_limit
    ):
        reasons.append("EXPIRING_SOON")
    if row["pass_count"] > 0 and row["total_remaining_sessions"] == 0:
        reasons.append("ALL_PASSES_EXHAUSTED")
    if (
        row["available_count"] == 0
        and row["expired_pass_count"] > 0
        and row["last_completed_at"] is not None
        and row["last_completed_at"][:10] >= recent_threshold
    ):
        reasons.append("EXPIRED_WITH_RECENT_ATTENDANCE")
    return reasons


def list_reregistration_candidates(
    academy_id: int,
    *,
    max_remaining: int,
    expiring_within_days: int,
    recent_attendance_days: int,
    limit: int,
    offset: int,
    sort: str,
    order: str,
) -> dict[str, Any]:
    """재등록 상담이 필요한 수강생 후보를 사유 코드와 함께 조회한다."""
    today = date.fromisoformat(_today())
    expiring_limit = (
        today + timedelta(days=expiring_within_days)
    ).isoformat()
    recent_threshold = (
        today - timedelta(days=recent_attendance_days)
    ).isoformat()
    today_text = today.isoformat()
    ordering = _sort_clause(sort, order, REREGISTRATION_SORT_FIELDS)
    aggregate_sql = """
        SELECT
            s.id AS student_id,
            s.name AS student_name,
            s.phone AS student_phone,
            s.expire_date AS student_expire_date,
            COUNT(sp.id) AS pass_count,
            COALESCE(SUM(sp.remaining_sessions), 0)
                AS total_remaining_sessions,
            COALESCE(SUM(CASE
                WHEN sp.remaining_sessions > 0 AND sp.expire_date >= ?
                THEN 1 ELSE 0
            END), 0) AS available_count,
            COALESCE(SUM(CASE
                WHEN sp.remaining_sessions > 0 AND sp.expire_date >= ?
                THEN sp.remaining_sessions ELSE 0
            END), 0) AS available_remaining_sessions,
            MIN(CASE
                WHEN sp.remaining_sessions > 0 AND sp.expire_date >= ?
                THEN sp.expire_date
            END) AS nearest_expire_date,
            COALESCE(SUM(CASE
                WHEN sp.expire_date < ? THEN 1 ELSE 0
            END), 0) AS expired_pass_count,
            (
                SELECT MAX(ar.completed_at)
                FROM attendance_records AS ar
                WHERE ar.student_id = s.id AND ar.status = 'COMPLETED'
            ) AS last_completed_at
        FROM students AS s
        LEFT JOIN student_passes AS sp ON sp.student_id = s.id
        WHERE s.academy_id = ?
        GROUP BY s.id
    """
    candidate_sql = f"""
        SELECT *
        FROM ({aggregate_sql})
        WHERE (available_count > 0
               AND available_remaining_sessions <= ?)
           OR (available_count > 0
               AND nearest_expire_date IS NOT NULL
               AND nearest_expire_date <= ?)
           OR (pass_count > 0 AND total_remaining_sessions = 0)
           OR (available_count = 0
               AND expired_pass_count > 0
               AND last_completed_at IS NOT NULL
               AND substr(last_completed_at, 1, 10) >= ?)
    """
    parameters = (
        today_text,
        today_text,
        today_text,
        today_text,
        academy_id,
        max_remaining,
        expiring_limit,
        recent_threshold,
    )
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        rows = connection.execute(
            f"{candidate_sql} ORDER BY {ordering} LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        ).fetchall()
        total = connection.execute(
            f"SELECT COUNT(*) FROM ({candidate_sql})",
            parameters,
        ).fetchone()[0]
        items = []
        for row in rows:
            items.append(
                {
                    "student_id": row["student_id"],
                    "student_name": row["student_name"],
                    "student_phone": row["student_phone"],
                    "student_expire_date": row["student_expire_date"],
                    "pass_count": row["pass_count"],
                    "remaining_sessions": row[
                        "available_remaining_sessions"
                    ],
                    "total_remaining_sessions": row[
                        "total_remaining_sessions"
                    ],
                    "available_pass_count": row["available_count"],
                    "nearest_expire_date": row["nearest_expire_date"],
                    "last_completed_at": row["last_completed_at"],
                    "reasons": _reregistration_reasons(
                        row,
                        max_remaining=max_remaining,
                        expiring_limit=expiring_limit,
                        recent_threshold=recent_threshold,
                    ),
                }
            )
        return {
            "criteria": {
                "max_remaining": max_remaining,
                "expiring_within_days": expiring_within_days,
                "recent_attendance_days": recent_attendance_days,
            },
            "items": items,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
        }
    finally:
        connection.close()


def check_ledger_consistency(academy_id: int) -> dict[str, Any]:
    """보유 수강권의 잔여 횟수와 수강 기록 차감 합계를 비교한다.

    조회 전용이며 어떤 값도 자동으로 고치지 않는다.
    """
    connection = _connect()
    try:
        _get_academy_row(connection, academy_id)
        rows = connection.execute(
            """
            SELECT
                sp.id AS student_pass_id,
                sp.student_id AS student_id,
                s.name AS student_name,
                sp.pass_type_name_snapshot AS pass_type_name,
                sp.total_sessions AS total_sessions,
                sp.remaining_sessions AS stored_remaining_sessions,
                sp.total_sessions + COALESCE((
                    SELECT SUM(ar.session_delta)
                    FROM attendance_records AS ar
                    WHERE ar.student_pass_id = sp.id
                ), 0) AS expected_remaining_sessions
            FROM student_passes AS sp
            JOIN students AS s ON s.id = sp.student_id
            WHERE s.academy_id = ?
            ORDER BY sp.id ASC
            """,
            (academy_id,),
        ).fetchall()
        items = [
            {
                **dict(row),
                "difference": (
                    row["stored_remaining_sessions"]
                    - row["expected_remaining_sessions"]
                ),
            }
            for row in rows
            if row["stored_remaining_sessions"]
            != row["expected_remaining_sessions"]
        ]
        return {
            "academy_id": academy_id,
            "checked_count": len(rows),
            "mismatch_count": len(items),
            "items": items,
        }
    finally:
        connection.close()
