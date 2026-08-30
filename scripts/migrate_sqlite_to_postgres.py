from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database import connection, database_backend, initialize_database


TABLES = (
    "profiles",
    "lab_reports",
    "diet_plans",
    "food_logs",
    "measurements",
    "care_reviews",
    "alerts",
    "users",
    "email_otp_rate_limits",
    "dietitian_customer_links",
    "clinical_questionnaires",
    "questionnaire_answers",
    "clinical_messages",
    "meal_schedule",
    "clinical_notes",
    "clinical_prescriptions",
)


def migrate(source_path: Path) -> dict[str, int]:
    if database_backend()["engine"] != "PostgreSQL":
        raise RuntimeError("Set NUTRIPULSE_DATABASE_URL before running this migration.")
    if not source_path.is_file():
        raise FileNotFoundError(f"SQLite backup not found: {source_path}")

    initialize_database()
    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    try:
        with connection() as target:
            for table_name in TABLES:
                exists = source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                ).fetchone()
                if not exists:
                    counts[table_name] = 0
                    continue
                columns = [
                    str(row["name"])
                    for row in source.execute(f"PRAGMA table_info({table_name})")
                ]
                rows = source.execute(f"SELECT * FROM {table_name}").fetchall()
                if not columns or not rows:
                    counts[table_name] = 0
                    continue
                placeholders = ", ".join("?" for _ in columns)
                sql = (
                    f"INSERT INTO {table_name} ({', '.join(columns)}) "
                    f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                )
                imported = 0
                for row in rows:
                    cursor = target.execute(sql, tuple(row[column] for column in columns))
                    imported += max(0, int(cursor.rowcount))
                counts[table_name] = imported
    finally:
        source.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a private NutriPulse SQLite backup into the configured PostgreSQL database.",
    )
    parser.add_argument("sqlite_backup", type=Path, help="Path to the private nutripulse.db backup")
    args = parser.parse_args()
    counts = migrate(args.sqlite_backup.expanduser().resolve())
    for table_name, count in counts.items():
        print(f"{table_name}: {count} imported")
    print(f"Migration complete: {sum(counts.values())} rows imported without overwriting existing records.")


if __name__ == "__main__":
    main()
