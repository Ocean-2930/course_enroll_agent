"""수강권 장부 SQLite 스키마를 정의한다."""

import sqlite3


SCHEMA_VERSION = 5

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
        -- 이 수강권으로 한 번 수강할 때의 기본 수업 시간(분).
        session_duration_minutes INTEGER NOT NULL DEFAULT 60
            CHECK (session_duration_minutes > 0),
        sort_index INTEGER NOT NULL DEFAULT 0,
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
        -- 구매 시점의 1회 수업 시간(분). 원본 종류가 바뀌어도 유지된다.
        session_duration_minutes_snapshot INTEGER NOT NULL
            CHECK (session_duration_minutes_snapshot > 0),
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
        -- 예약 종료 시각. 클라이언트가 보내지 않고 서버가 수강권
        -- session_duration_minutes_snapshot 으로 계산한다.
        scheduled_end_at TEXT NOT NULL,
        status TEXT NOT NULL CHECK (
            status IN ('RESERVED', 'CHECKED_IN', 'COMPLETED', 'CANCELLED')
        ),
        session_delta INTEGER NOT NULL DEFAULT 0
            CHECK (session_delta IN (-1, 0)),
        checked_in_at TEXT,
        checked_out_at TEXT,
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
            OR (status = 'CHECKED_IN' AND session_delta = 0)
            OR (status = 'COMPLETED' AND session_delta = -1)
            OR (status = 'CANCELLED' AND session_delta = 0)
        ),
        CHECK (status != 'COMPLETED' OR completed_at IS NOT NULL),
        CHECK (status != 'CANCELLED' OR cancelled_at IS NOT NULL),
        -- 상태별 체크인·퇴실 시각 규칙
        CHECK (
            status != 'RESERVED'
            OR (checked_in_at IS NULL AND checked_out_at IS NULL)
        ),
        CHECK (
            status != 'CHECKED_IN'
            OR (checked_in_at IS NOT NULL AND checked_out_at IS NULL)
        ),
        CHECK (
            status != 'COMPLETED'
            OR (checked_in_at IS NOT NULL AND checked_out_at IS NOT NULL)
        ),
        CHECK (status != 'CANCELLED' OR checked_out_at IS NULL)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        academy_id INTEGER NOT NULL,
        student_id INTEGER,
        student_name_snapshot TEXT NOT NULL,
        category TEXT NOT NULL CHECK (
            category IN (
                'PASS',
                'RESERVATION',
                'ATTENDANCE',
                'CHECK_IN_OUT',
                'DEDUCTION_ERROR',
                'EXTENSION',
                'REFUND',
                'FACILITY',
                'OTHER'
            )
        ),
        title TEXT NOT NULL,
        status TEXT NOT NULL CHECK (
            status IN ('OPEN', 'ANSWERED', 'CLOSED')
        ),
        related_student_pass_id INTEGER,
        related_attendance_record_id INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        closed_at TEXT,
        FOREIGN KEY (academy_id) REFERENCES academies(id)
            ON DELETE CASCADE,
        FOREIGN KEY (student_id) REFERENCES students(id)
            ON DELETE SET NULL,
        FOREIGN KEY (related_student_pass_id) REFERENCES student_passes(id)
            ON DELETE SET NULL,
        FOREIGN KEY (related_attendance_record_id)
            REFERENCES attendance_records(id)
            ON DELETE SET NULL,
        CHECK (status != 'CLOSED' OR closed_at IS NOT NULL)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inquiry_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inquiry_id INTEGER NOT NULL,
        sender_type TEXT NOT NULL CHECK (
            sender_type IN ('STUDENT', 'ACADEMY')
        ),
        message TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
            ON DELETE CASCADE
    )
    """,
)

INDEX_STATEMENTS = (
    """
    CREATE INDEX IF NOT EXISTS idx_pass_types_academy_sort
    ON pass_types (academy_id, sort_index)
    """,
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
    """
    CREATE INDEX IF NOT EXISTS idx_inquiries_academy_id
    ON inquiries (academy_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inquiries_student_id
    ON inquiries (student_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inquiries_academy_status
    ON inquiries (academy_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inquiries_student_status
    ON inquiries (student_id, status)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inquiries_created_at
    ON inquiries (created_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inquiry_messages_inquiry_id
    ON inquiry_messages (inquiry_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_inquiry_messages_inquiry_created
    ON inquiry_messages (inquiry_id, created_at)
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
