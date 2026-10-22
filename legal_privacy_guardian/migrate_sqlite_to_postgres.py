import argparse
from contextlib import closing
import json
import os
from datetime import datetime
from pathlib import Path
import sqlite3

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from database import init_db


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "instance" / "guardian.sqlite3"


def migrate(sqlite_path: Path, database_url: str) -> tuple[int, int]:
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"Base SQLite introuvable : {sqlite_path}")

    with closing(sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)) as source:
        source.row_factory = sqlite3.Row
        table = source.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'scan_reports'"
        ).fetchone()
        if table is None:
            raise ValueError("La base SQLite ne contient pas la table scan_reports.")
        rows = source.execute(
            "SELECT id, filename, scanned_at, findings FROM scan_reports ORDER BY id"
        ).fetchall()

    init_db(database_url)
    migrated = 0
    already_present = 0
    with psycopg.connect(database_url, row_factory=dict_row) as target:
        for row in rows:
            findings = json.loads(row["findings"])
            existing = target.execute(
                """
                SELECT filename, scanned_at, findings
                FROM scan_reports
                WHERE id = %s
                """,
                (row["id"],),
            ).fetchone()
            if existing is not None:
                existing_timestamp = existing["scanned_at"].strftime("%Y-%m-%d %H:%M:%S")
                if (
                    existing["filename"] != row["filename"]
                    or existing_timestamp != row["scanned_at"]
                    or existing["findings"] != findings
                ):
                    raise ValueError(
                        f"Conflit avec le rapport PostgreSQL id={row['id']}; "
                        "aucune migration n’a été validée."
                    )
                already_present += 1
                continue

            target.execute(
                """
                INSERT INTO scan_reports (id, filename, scanned_at, findings)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    row["id"],
                    row["filename"],
                    datetime.fromisoformat(row["scanned_at"]),
                    Jsonb(findings),
                ),
            )
            migrated += 1

        target.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('scan_reports', 'id'),
                GREATEST(COALESCE(MAX(id), 1), 1),
                MAX(id) IS NOT NULL
            )
            FROM scan_reports
            """
        )

    return migrated, already_present


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copie l’historique SQLite vers PostgreSQL sans écraser les conflits."
    )
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=DEFAULT_SQLITE_PATH,
        help=f"Base source (défaut : {DEFAULT_SQLITE_PATH})",
    )
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("Définissez DATABASE_URL pour la connexion PostgreSQL locale.")

    migrated, already_present = migrate(args.sqlite, database_url)
    print(
        f"Migration terminée : {migrated} rapport(s) copié(s), "
        f"{already_present} déjà présent(s) et vérifié(s)."
    )


if __name__ == "__main__":
    main()
