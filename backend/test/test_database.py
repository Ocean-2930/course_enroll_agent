"""수강권 장부 스키마의 제약조건과 삭제 정책을 검증한다."""

from pathlib import Path
import sqlite3
import unittest

from database.connection import connect_database
from database.schema import SCHEMA_VERSION, setup_schema
from init_db import init_db


class DatabaseSchemaTest(unittest.TestCase):
    """메모리 SQLite에서 실제 외래 키 동작을 검증한다."""

    def setUp(self) -> None:
        self.connection = connect_database(Path(":memory:"))
        setup_schema(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def _create_ledger(self) -> tuple[int, int, int, int, int]:
        academy_id = self.connection.execute(
            "INSERT INTO academies (name) VALUES (?)",
            ("테스트 아카데미",),
        ).lastrowid
        pass_type_id = self.connection.execute(
            """
            INSERT INTO pass_types (
                academy_id, name, total_sessions, validity_days, price,
                session_duration_minutes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (academy_id, "그룹 필라테스 10회권", 10, 90, 150000, 50),
        ).lastrowid
        student_id = self.connection.execute(
            """
            INSERT INTO students (academy_id, name, phone, expire_date)
            VALUES (?, ?, ?, ?)
            """,
            (academy_id, "홍길동", "010-0000-0000", "2026-10-28"),
        ).lastrowid
        student_pass_id = self.connection.execute(
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
                expire_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                pass_type_id,
                pass_type_id,
                "그룹 필라테스 10회권",
                10,
                10,
                90,
                150000,
                50,
                "2026-07-30",
                "2026-10-28",
            ),
        ).lastrowid
        attendance_id = self.connection.execute(
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
                session_delta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RESERVED', 0)
            """,
            (
                academy_id,
                student_id,
                student_pass_id,
                pass_type_id,
                "그룹 필라테스 10회권",
                "홍길동",
                "오전 그룹 수업",
                "2026-08-01T10:00:00",
                "2026-08-01T10:50:00",
            ),
        ).lastrowid
        self.connection.commit()
        return (
            academy_id,
            pass_type_id,
            student_id,
            student_pass_id,
            attendance_id,
        )

    def _create_inquiry(
        self,
        academy_id: int,
        student_id: int,
        *,
        student_pass_id: int | None = None,
        attendance_id: int | None = None,
    ) -> tuple[int, int]:
        inquiry_id = self.connection.execute(
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
            ) VALUES (?, ?, ?, 'DEDUCTION_ERROR', ?, 'OPEN', ?, ?)
            """,
            (
                academy_id,
                student_id,
                "홍길동",
                "횟수가 잘못 차감된 것 같습니다.",
                student_pass_id,
                attendance_id,
            ),
        ).lastrowid
        message_id = self.connection.execute(
            """
            INSERT INTO inquiry_messages (inquiry_id, sender_type, message)
            VALUES (?, 'STUDENT', ?)
            """,
            (inquiry_id, "오늘 수업이 두 번 차감됐습니다."),
        ).lastrowid
        self.connection.commit()
        return inquiry_id, message_id

    def test_foreign_keys_are_enabled(self) -> None:
        enabled = self.connection.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(enabled, 1)

    def test_deleting_pass_type_keeps_issued_pass_and_snapshots(self) -> None:
        _, pass_type_id, _, student_pass_id, _ = self._create_ledger()

        self.connection.execute(
            "DELETE FROM pass_types WHERE id = ?", (pass_type_id,)
        )
        row = self.connection.execute(
            """
            SELECT pass_type_id,
                   pass_type_id_snapshot,
                   pass_type_name_snapshot,
                   session_duration_minutes_snapshot
            FROM student_passes
            WHERE id = ?
            """,
            (student_pass_id,),
        ).fetchone()

        # 원본 종류가 사라져도 구매 시점 수업 시간 스냅샷은 유지된다.
        self.assertEqual(
            tuple(row), (None, pass_type_id, "그룹 필라테스 10회권", 50)
        )

    def test_deleting_student_pass_keeps_attendance_and_snapshots(self) -> None:
        _, pass_type_id, _, student_pass_id, attendance_id = (
            self._create_ledger()
        )

        self.connection.execute(
            "DELETE FROM student_passes WHERE id = ?", (student_pass_id,)
        )
        row = self.connection.execute(
            """
            SELECT student_pass_id,
                   pass_type_id_snapshot,
                   pass_type_name_snapshot
            FROM attendance_records
            WHERE id = ?
            """,
            (attendance_id,),
        ).fetchone()

        self.assertEqual(
            tuple(row), (None, pass_type_id, "그룹 필라테스 10회권")
        )

    def test_deleting_student_cascades_pass_but_keeps_attendance(self) -> None:
        _, _, student_id, student_pass_id, attendance_id = (
            self._create_ledger()
        )

        self.connection.execute(
            "DELETE FROM students WHERE id = ?", (student_id,)
        )

        issued_pass = self.connection.execute(
            "SELECT id FROM student_passes WHERE id = ?", (student_pass_id,)
        ).fetchone()
        attendance = self.connection.execute(
            """
            SELECT student_id, student_pass_id, student_name_snapshot
            FROM attendance_records
            WHERE id = ?
            """,
            (attendance_id,),
        ).fetchone()
        self.assertIsNone(issued_pass)
        self.assertEqual(tuple(attendance), (None, None, "홍길동"))

    def test_deleting_academy_cascades_all_child_data(self) -> None:
        academy_id, _, student_id, _, _ = self._create_ledger()
        self._create_inquiry(academy_id, student_id)

        self.connection.execute(
            "DELETE FROM academies WHERE id = ?", (academy_id,)
        )

        for table_name in (
            "pass_types",
            "students",
            "student_passes",
            "attendance_records",
            "inquiries",
            "inquiry_messages",
        ):
            with self.subTest(table_name=table_name):
                row_count = self.connection.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                self.assertEqual(row_count, 0)

    def test_remaining_sessions_constraints(self) -> None:
        _, pass_type_id, student_id, _, _ = self._create_ledger()

        for remaining_sessions in (-1, 11):
            with self.subTest(remaining_sessions=remaining_sessions):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
                        """
                        INSERT INTO student_passes (
                            student_id,
                            pass_type_id,
                            pass_type_id_snapshot,
                            pass_type_name_snapshot,
                            total_sessions,
                            remaining_sessions,
                            validity_days_snapshot,
                            session_duration_minutes_snapshot,
                            purchased_at,
                            expire_date
                        ) VALUES (?, ?, ?, ?, 10, ?, 90, 50, ?, ?)
                        """,
                        (
                            student_id,
                            pass_type_id,
                            pass_type_id,
                            "제약조건 테스트권",
                            remaining_sessions,
                            "2026-07-30",
                            "2026-10-28",
                        ),
                    )

    def test_session_duration_must_be_positive(self) -> None:
        academy_id, pass_type_id, student_id, _, _ = self._create_ledger()

        with self.subTest("pass_types"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    """
                    INSERT INTO pass_types (
                        academy_id, name, total_sessions, validity_days,
                        price, session_duration_minutes
                    ) VALUES (?, ?, 10, 90, 0, 0)
                    """,
                    (academy_id, "잘못된 수업 시간권"),
                )

        with self.subTest("student_passes"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    """
                    INSERT INTO student_passes (
                        student_id,
                        pass_type_id,
                        pass_type_id_snapshot,
                        pass_type_name_snapshot,
                        total_sessions,
                        remaining_sessions,
                        validity_days_snapshot,
                        session_duration_minutes_snapshot,
                        purchased_at,
                        expire_date
                    ) VALUES (?, ?, ?, ?, 10, 10, 90, 0, ?, ?)
                    """,
                    (
                        student_id,
                        pass_type_id,
                        pass_type_id,
                        "잘못된 스냅샷권",
                        "2026-07-30",
                        "2026-10-28",
                    ),
                )

    def test_pass_types_session_duration_defaults_to_60(self) -> None:
        academy_id, _, _, _, _ = self._create_ledger()
        pass_type_id = self.connection.execute(
            """
            INSERT INTO pass_types (
                academy_id, name, total_sessions, validity_days, price
            ) VALUES (?, ?, 10, 90, 100000)
            """,
            (academy_id, "기본 시간권"),
        ).lastrowid
        duration = self.connection.execute(
            "SELECT session_duration_minutes FROM pass_types WHERE id = ?",
            (pass_type_id,),
        ).fetchone()[0]
        self.assertEqual(duration, 60)

    def _insert_attendance(
        self,
        academy_id: int,
        student_id: int,
        student_pass_id: int,
        pass_type_id: int,
        *,
        status: str,
        session_delta: int,
        checked_in_at: str | None = None,
        checked_out_at: str | None = None,
        completed_at: str | None = None,
        cancelled_at: str | None = None,
    ) -> int:
        return self.connection.execute(
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
                checked_in_at,
                checked_out_at,
                completed_at,
                cancelled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                academy_id,
                student_id,
                student_pass_id,
                pass_type_id,
                "그룹 필라테스 10회권",
                "홍길동",
                "제약조건 테스트 수업",
                "2026-08-02T10:00:00",
                "2026-08-02T10:50:00",
                status,
                session_delta,
                checked_in_at,
                checked_out_at,
                completed_at,
                cancelled_at,
            ),
        ).lastrowid

    def test_attendance_status_and_delta_constraints(self) -> None:
        academy_id, pass_type_id, student_id, student_pass_id, _ = (
            self._create_ledger()
        )
        invalid_values = (
            ("UNKNOWN", 0),
            ("RESERVED", -1),
            ("CHECKED_IN", -1),
            ("COMPLETED", 0),
            ("CANCELLED", -1),
        )

        for status, session_delta in invalid_values:
            with self.subTest(status=status, session_delta=session_delta):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._insert_attendance(
                        academy_id,
                        student_id,
                        student_pass_id,
                        pass_type_id,
                        status=status,
                        session_delta=session_delta,
                        checked_in_at="2026-08-02T10:00:00",
                        checked_out_at="2026-08-02T10:50:00",
                        completed_at="2026-08-02T10:50:00",
                        cancelled_at="2026-08-02T10:50:00",
                    )

    def test_checked_in_status_is_allowed(self) -> None:
        academy_id, pass_type_id, student_id, student_pass_id, _ = (
            self._create_ledger()
        )
        attendance_id = self._insert_attendance(
            academy_id,
            student_id,
            student_pass_id,
            pass_type_id,
            status="CHECKED_IN",
            session_delta=0,
            checked_in_at="2026-08-02T09:55:00",
        )
        row = self.connection.execute(
            """
            SELECT status, session_delta, checked_in_at, checked_out_at
            FROM attendance_records
            WHERE id = ?
            """,
            (attendance_id,),
        ).fetchone()
        self.assertEqual(
            tuple(row), ("CHECKED_IN", 0, "2026-08-02T09:55:00", None)
        )

    def test_attendance_time_field_rules(self) -> None:
        academy_id, pass_type_id, student_id, student_pass_id, _ = (
            self._create_ledger()
        )
        invalid_rows = (
            # 예약 상태에는 체크인 시각이 없어야 한다.
            {
                "status": "RESERVED",
                "session_delta": 0,
                "checked_in_at": "2026-08-02T09:55:00",
            },
            # 체크인 상태에는 체크인 시각이 있어야 한다.
            {"status": "CHECKED_IN", "session_delta": 0},
            # 체크인 상태에는 퇴실 시각이 없어야 한다.
            {
                "status": "CHECKED_IN",
                "session_delta": 0,
                "checked_in_at": "2026-08-02T09:55:00",
                "checked_out_at": "2026-08-02T10:50:00",
            },
            # 완료 상태에는 체크인·퇴실 시각이 모두 있어야 한다.
            {
                "status": "COMPLETED",
                "session_delta": -1,
                "completed_at": "2026-08-02T10:50:00",
            },
            # 취소 상태에는 퇴실 시각이 없어야 한다.
            {
                "status": "CANCELLED",
                "session_delta": 0,
                "cancelled_at": "2026-08-02T10:50:00",
                "checked_out_at": "2026-08-02T10:50:00",
            },
        )
        for index, values in enumerate(invalid_rows):
            with self.subTest(case=index, status=values["status"]):
                with self.assertRaises(sqlite3.IntegrityError):
                    self._insert_attendance(
                        academy_id,
                        student_id,
                        student_pass_id,
                        pass_type_id,
                        **values,
                    )

    def test_inquiry_constraints_and_delete_policy(self) -> None:
        academy_id, _, student_id, student_pass_id, attendance_id = (
            self._create_ledger()
        )
        inquiry_id, _ = self._create_inquiry(
            academy_id,
            student_id,
            student_pass_id=student_pass_id,
            attendance_id=attendance_id,
        )

        with self.subTest("잘못된 문의 유형"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    """
                    INSERT INTO inquiries (
                        academy_id, student_id, student_name_snapshot,
                        category, title, status
                    ) VALUES (?, ?, '홍길동', 'UNKNOWN', '제목', 'OPEN')
                    """,
                    (academy_id, student_id),
                )

        with self.subTest("잘못된 문의 상태"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    """
                    INSERT INTO inquiries (
                        academy_id, student_id, student_name_snapshot,
                        category, title, status
                    ) VALUES (?, ?, '홍길동', 'OTHER', '제목', 'UNKNOWN')
                    """,
                    (academy_id, student_id),
                )

        with self.subTest("잘못된 발신자"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute(
                    """
                    INSERT INTO inquiry_messages (
                        inquiry_id, sender_type, message
                    ) VALUES (?, 'MANAGER', '메시지')
                    """,
                    (inquiry_id,),
                )

        # 수강권을 지워도 문의는 남고 연결만 끊긴다.
        self.connection.execute(
            "DELETE FROM student_passes WHERE id = ?", (student_pass_id,)
        )
        related_pass_id = self.connection.execute(
            "SELECT related_student_pass_id FROM inquiries WHERE id = ?",
            (inquiry_id,),
        ).fetchone()[0]
        self.assertIsNone(related_pass_id)

        # 수강생을 지워도 문의와 이름 스냅샷은 보존된다.
        self.connection.execute(
            "DELETE FROM students WHERE id = ?", (student_id,)
        )
        row = self.connection.execute(
            "SELECT student_id, student_name_snapshot FROM inquiries WHERE id = ?",
            (inquiry_id,),
        ).fetchone()
        self.assertEqual(tuple(row), (None, "홍길동"))

        # 문의를 지우면 메시지도 함께 사라진다.
        self.connection.execute(
            "DELETE FROM inquiries WHERE id = ?", (inquiry_id,)
        )
        message_count = self.connection.execute(
            "SELECT COUNT(*) FROM inquiry_messages WHERE inquiry_id = ?",
            (inquiry_id,),
        ).fetchone()[0]
        self.assertEqual(message_count, 0)

    def test_init_db_deletes_existing_database_and_creates_fresh_schema(
        self,
    ) -> None:
        backend_directory = Path(__file__).resolve().parent
        database_path = backend_directory / "test_init_reset.db"
        sidecar_paths = (
            Path(f"{database_path}-journal"),
            Path(f"{database_path}-shm"),
            Path(f"{database_path}-wal"),
        )
        try:
            init_db(database_path)
            connection = connect_database(database_path)
            try:
                connection.execute(
                    "INSERT INTO academies (name) VALUES (?)",
                    ("삭제 대상 학원",),
                )
                connection.commit()
            finally:
                connection.close()

            for sidecar_path in sidecar_paths:
                sidecar_path.write_text("삭제 대상", encoding="utf-8")

            init_db(database_path)

            connection = connect_database(database_path)
            try:
                academy_count = connection.execute(
                    "SELECT COUNT(*) FROM academies"
                ).fetchone()[0]
                schema_version = connection.execute(
                    """
                    SELECT value
                    FROM app_metadata
                    WHERE key = 'schema_version'
                    """
                ).fetchone()[0]
            finally:
                connection.close()

            self.assertEqual(academy_count, 0)
            self.assertEqual(schema_version, str(SCHEMA_VERSION))
            for sidecar_path in sidecar_paths:
                self.assertFalse(sidecar_path.exists())
        finally:
            database_path.unlink(missing_ok=True)
            for sidecar_path in sidecar_paths:
                sidecar_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
