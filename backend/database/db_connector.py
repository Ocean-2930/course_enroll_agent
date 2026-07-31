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
                        total_sessions, validity_days, price, sort_index
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        academy_id,
                        data["name"],
                        data.get("description"),
                        data["total_sessions"],
                        data["validity_days"],
                        data.get("price", 0),
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
                    purchased_at,
                    started_at,
                    expire_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
) -> None:
    connection = _connect()
    try:
        row = _get_student_pass_row(
            connection,
            academy_id,
            student_id,
            student_pass_id,
        )
        if row["remaining_sessions"] > 0:
            raise _error(
                409,
                "STUDENT_PASS_HAS_REMAINING_SESSIONS",
                "남은 횟수가 있는 수강권은 삭제할 수 없습니다.",
                student_pass_id=student_pass_id,
                remaining_sessions=row["remaining_sessions"],
            )
        with connection:
            connection.execute(
                """
                DELETE FROM student_passes
                WHERE id = ? AND student_id = ?
                """,
                (student_pass_id, student_id),
            )
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
                    status,
                    session_delta,
                    memo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RESERVED', 0, ?)
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
                    completed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'RESERVED'
                """,
                (completion_time, attendance_record_id),
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
            connection.execute(
                """
                UPDATE attendance_records
                SET status = 'CANCELLED',
                    session_delta = 0,
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
