"""수강권 장부 스키마의 제약조건과 삭제 정책을 검증한다."""

from pathlib import Path
import sqlite3
import unittest

from database.connection import connect_database
from database.schema import setup_schema
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
                academy_id, name, total_sessions, validity_days, price
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (academy_id, "그룹 필라테스 10회권", 10, 90, 150000),
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
                purchased_at,
                expire_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                status,
                session_delta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'RESERVED', 0)
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
            SELECT pass_type_id, pass_type_id_snapshot, pass_type_name_snapshot
            FROM student_passes
            WHERE id = ?
            """,
            (student_pass_id,),
        ).fetchone()

        self.assertEqual(
            tuple(row), (None, pass_type_id, "그룹 필라테스 10회권")
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
        academy_id, _, _, _, _ = (
            self._create_ledger()
        )

        self.connection.execute(
            "DELETE FROM academies WHERE id = ?", (academy_id,)
        )

        for table_name in (
            "pass_types",
            "students",
            "student_passes",
            "attendance_records",
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
                            purchased_at,
                            expire_date
                        ) VALUES (?, ?, ?, ?, 10, ?, 90, ?, ?)
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

    def test_attendance_status_and_delta_constraints(self) -> None:
        academy_id, pass_type_id, student_id, student_pass_id, _ = (
            self._create_ledger()
        )
        invalid_values = (
            ("UNKNOWN", 0),
            ("RESERVED", -1),
            ("COMPLETED", 0),
            ("CANCELLED", -1),
        )

        for status, session_delta in invalid_values:
            with self.subTest(status=status, session_delta=session_delta):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.connection.execute(
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
                            session_delta
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            status,
                            session_delta,
                        ),
                    )

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
            self.assertEqual(schema_version, "3")
            for sidecar_path in sidecar_paths:
                self.assertFalse(sidecar_path.exists())
        finally:
            database_path.unlink(missing_ok=True)
            for sidecar_path in sidecar_paths:
                sidecar_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
