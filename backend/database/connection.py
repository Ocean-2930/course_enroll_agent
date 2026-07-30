"""SQLite 연결 생성을 담당한다."""

from pathlib import Path
import sqlite3


DATABASE_PATH = Path(__file__).resolve().parent.parent / "course_enroll.db"


def connect_database(database_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    """외래 키 검사를 활성화한 새 SQLite 연결을 반환한다."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")

    foreign_keys_enabled = connection.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]
    if foreign_keys_enabled != 1:
        connection.close()
        raise RuntimeError("SQLite 외래 키 기능을 활성화하지 못했습니다.")

    return connection
