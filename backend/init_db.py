"""백엔드 디렉터리에 수강권 장부 SQLite 데이터베이스를 초기화한다."""

from pathlib import Path

from database.connection import DATABASE_PATH, connect_database
from database.schema import setup_schema


def _delete_database_files(database_path: Path) -> None:
    """기존 SQLite 본체와 부속 파일을 삭제한다."""
    related_paths = (
        database_path,
        Path(f"{database_path}-journal"),
        Path(f"{database_path}-shm"),
        Path(f"{database_path}-wal"),
    )
    for path in related_paths:
        path.unlink(missing_ok=True)


def init_db(database_path: Path = DATABASE_PATH) -> Path:
    """기존 SQLite를 삭제하고 최신 전체 스키마로 새로 생성한다."""
    _delete_database_files(database_path)

    connection = connect_database(database_path)
    try:
        setup_schema(connection)
    finally:
        connection.close()

    return database_path


if __name__ == "__main__":
    database_path = init_db()
    print(f"SQLite 데이터베이스를 새로 생성했습니다: {database_path}")
