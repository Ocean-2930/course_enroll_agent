"""수강권 장부 SQLite 스키마를 정의한다."""

import sqlite3


SCHEMA_VERSION = 3

TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS app_metadata (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS academies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pass_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        academy_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        total_sessions INTEGER NOT NULL CHECK (total_sessions > 0),
        validity_days INTEGER NOT NULL CHECK (validity_days > 0),
        price INTEGER NOT NULL DEFAULT 0 CHECK (price >= 0),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (academy_id) REFERENCES academies(id)
            ON DELETE CASCADE,
        UNIQUE (academy_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        academy_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        memo TEXT,
        expire_date TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (academy_id) REFERENCES academies(id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS student_passes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        pass_type_id INTEGER,
        pass_type_id_snapshot INTEGER NOT NULL,
        pass_type_name_snapshot TEXT NOT NULL,
        total_sessions INTEGER NOT NULL CHECK (total_sessions > 0),
        remaining_sessions INTEGER NOT NULL CHECK (
            remaining_sessions >= 0
            AND remaining_sessions <= total_sessions
        ),
        validity_days_snapshot INTEGER NOT NULL
            CHECK (validity_days_snapshot > 0),
        price_snapshot INTEGER NOT NULL DEFAULT 0
            CHECK (price_snapshot >= 0),
        purchased_at TEXT NOT NULL,
        started_at TEXT,
        expire_date TEXT NOT NULL CHECK (expire_date >= purchased_at),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(id)
            ON DELETE CASCADE,
        FOREIGN KEY (pass_type_id) REFERENCES pass_types(id)
            ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attendance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        academy_id INTEGER,
        student_id INTEGER,
        student_pass_id INTEGER,
        pass_type_id_snapshot INTEGER NOT NULL,
        pass_type_name_snapshot TEXT NOT NULL,
        student_name_snapshot TEXT NOT NULL,
        class_name TEXT NOT NULL,
        scheduled_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK (
            status IN ('RESERVED', 'COMPLETED', 'CANCELLED')
        ),
        session_delta INTEGER NOT NULL DEFAULT 0
            CHECK (session_delta IN (-1, 0)),
        cancelled_at TEXT,
        completed_at TEXT,
        memo TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (academy_id) REFERENCES academies(id)
            ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id)
            ON DELETE SET NULL,
        FOREIGN KEY (student_pass_id) REFERENCES student_passes(id)
            ON DELETE SET NULL,
        CHECK (
            (status = 'RESERVED' AND session_delta = 0)
            OR (status = 'COMPLETED' AND session_delta = -1)
            OR (status = 'CANCELLED' AND session_delta = 0)
        ),
        CHECK (status != 'COMPLETED' OR completed_at IS NOT NULL),
        CHECK (status != 'CANCELLED' OR cancelled_at IS NOT NULL)
    )
    """,
)

INDEX_STATEMENTS = (
    """
    CREATE INDEX IF NOT EXISTS idx_students_academy_name
    ON students (academy_id, name)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_students_academy_expire_date
    ON students (academy_id, expire_date)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_students_academy_phone
    ON students (academy_id, phone)
    WHERE phone IS NOT NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_passes_student_id
    ON student_passes (student_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_passes_pass_type_id
    ON student_passes (pass_type_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_passes_student_expire_date
    ON student_passes (student_id, expire_date)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_passes_student_remaining
    ON student_passes (student_id, remaining_sessions)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_passes_pass_type_snapshot
    ON student_passes (pass_type_id_snapshot)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_academy_id
    ON attendance_records (academy_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_student_id
    ON attendance_records (student_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_student_pass_id
    ON attendance_records (student_pass_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_pass_type_snapshot
    ON attendance_records (pass_type_id_snapshot)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_scheduled_at
    ON attendance_records (scheduled_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_academy_scheduled
    ON attendance_records (academy_id, scheduled_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_student_scheduled
    ON attendance_records (student_id, scheduled_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_student_pass_scheduled
    ON attendance_records (student_pass_id, scheduled_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_attendance_status_scheduled
    ON attendance_records (status, scheduled_at)
    """,
)


def setup_schema(connection: sqlite3.Connection) -> None:
    """빈 SQLite에 현재 전체 스키마를 단일 트랜잭션으로 설정한다."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in TABLE_STATEMENTS:
            connection.execute(statement)
        for statement in INDEX_STATEMENTS:
            connection.execute(statement)

        connection.execute(
            """
            INSERT INTO app_metadata (key, value)
            VALUES ('schema_version', ?)
            """,
            (str(SCHEMA_VERSION),),
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
