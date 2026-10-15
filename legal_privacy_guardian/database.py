from contextlib import closing
import json
import sqlite3
from pathlib import Path


def init_db(database_path: Path) -> None:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                findings TEXT NOT NULL
            )
            """
        )


def save_scan(database_path: Path, filename: str, findings: dict[str, int]) -> int:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        cursor = connection.execute(
            "INSERT INTO scan_reports (filename, findings) VALUES (?, ?)",
            (filename, json.dumps(findings, ensure_ascii=False)),
        )
        return int(cursor.lastrowid)


def get_scan(database_path: Path, scan_id: int) -> dict[str, object] | None:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, filename, scanned_at, findings FROM scan_reports WHERE id = ?",
            (scan_id,),
        ).fetchone()
    return _row_to_scan(row) if row else None


def delete_scan(database_path: Path, scan_id: int) -> bool:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        cursor = connection.execute("DELETE FROM scan_reports WHERE id = ?", (scan_id,))
        return cursor.rowcount > 0


def delete_all_scans(database_path: Path) -> int:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        cursor = connection.execute("DELETE FROM scan_reports")
        return cursor.rowcount


def list_recent_scans(database_path: Path, limit: int = 10) -> list[dict[str, object]]:
    limit = max(1, min(limit, 100))
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, filename, scanned_at, findings
            FROM scan_reports
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_scan(row) for row in rows]


def _row_to_scan(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "scanned_at": row["scanned_at"],
        "findings": json.loads(row["findings"]),
    }
