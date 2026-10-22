import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from migrate_sqlite_to_postgres import migrate


class FakeCursor:
    def __init__(self, row=None):
        self.row = row
        self.rowcount = 1
        self.lastrowid = None

    def fetchone(self):
        return self.row


class FakePostgresConnection:
    def __init__(self, rows=None):
        self.rows = rows or {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters=()):
        if "WHERE id = %s" in query:
            return FakeCursor(self.rows.get(parameters[0]))
        if query.lstrip().startswith("INSERT INTO scan_reports"):
            scan_id, filename, scanned_at, findings = parameters
            self.rows[scan_id] = {
                "filename": filename,
                "scanned_at": scanned_at,
                "findings": findings.obj,
            }
        return FakeCursor()


class SQLiteMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.sqlite_path = Path(self.temporary_directory.name) / "source.sqlite3"
        with closing(sqlite3.connect(self.sqlite_path)) as connection, connection:
            connection.execute(
                """
                CREATE TABLE scan_reports (
                    id INTEGER PRIMARY KEY,
                    filename TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    findings TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO scan_reports (id, filename, scanned_at, findings)
                VALUES (?, ?, ?, ?)
                """,
                (5, "contract.txt", "2026-10-21 11:00:00", '{"email": 2}'),
            )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_migration_is_idempotent_and_preserves_ids(self):
        target = FakePostgresConnection()
        with (
            patch("migrate_sqlite_to_postgres.init_db"),
            patch("migrate_sqlite_to_postgres.psycopg.connect", return_value=target),
        ):
            self.assertEqual(migrate(self.sqlite_path, "postgresql://local/db"), (1, 0))
            self.assertEqual(migrate(self.sqlite_path, "postgresql://local/db"), (0, 1))

        self.assertEqual(
            target.rows[5],
            {
                "filename": "contract.txt",
                "scanned_at": datetime(2026, 10, 21, 11, 0),
                "findings": {"email": 2},
            },
        )

    def test_migration_stops_on_conflicting_existing_id(self):
        target = FakePostgresConnection(
            {
                5: {
                    "filename": "different.txt",
                    "scanned_at": datetime(2026, 10, 21, 11, 0),
                    "findings": {"email": 2},
                }
            }
        )
        with (
            patch("migrate_sqlite_to_postgres.init_db"),
            patch("migrate_sqlite_to_postgres.psycopg.connect", return_value=target),
            self.assertRaisesRegex(ValueError, "Conflit.*id=5"),
        ):
            migrate(self.sqlite_path, "postgresql://local/db")

    def test_migration_requires_scan_table(self):
        empty_path = Path(self.temporary_directory.name) / "empty.sqlite3"
        sqlite3.connect(empty_path).close()

        with self.assertRaisesRegex(ValueError, "scan_reports"):
            migrate(empty_path, "postgresql://local/db")


if __name__ == "__main__":
    unittest.main()
