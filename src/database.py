from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date as date_type, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from .constants import DATABASE_PATH


def _configured_database_url() -> str:
    """Return the managed database URL without logging or exposing it."""
    return os.getenv("NUTRIPULSE_DATABASE_URL", "").strip()


def _uses_postgres(db_path: Path = DATABASE_PATH) -> bool:
    """Use PostgreSQL only for the application's default live database.

    Explicit database paths are intentionally kept on SQLite so local tools and
    isolated tests never connect to a production database by accident.
    """
    return bool(_configured_database_url()) and Path(db_path).resolve() == DATABASE_PATH.resolve()


def _postgres_sql(statement: str) -> str:
    """Translate the DB-API placeholder style used by SQLite to psycopg."""
    return statement.replace("?", "%s")


class _PostgresConnection:
    """Small compatibility adapter for the subset of DB-API used by NutriPulse."""

    def __init__(self, raw_connection: Any) -> None:
        self._raw_connection = raw_connection

    def execute(self, statement: str, parameters: tuple[Any, ...] | list[Any] = ()) -> Any:
        return self._raw_connection.execute(_postgres_sql(statement), parameters)


def database_backend(db_path: Path = DATABASE_PATH) -> dict[str, Any]:
    """Describe whether live records are safe across cloud app restarts."""
    if _uses_postgres(db_path):
        return {
            "engine": "PostgreSQL",
            "storage": "Managed cloud database",
            "cloud_persistent": True,
        }
    return {
        "engine": "SQLite",
        "storage": "Local database file",
        "cloud_persistent": False,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection(db_path: Path = DATABASE_PATH) -> Iterator[Any]:
    if _uses_postgres(db_path):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - exercised in deployment
            raise RuntimeError(
                "PostgreSQL storage is configured, but psycopg is not installed. "
                "Install the project requirements and restart NutriPulse."
            ) from exc

        raw_connection = psycopg.connect(_configured_database_url(), row_factory=dict_row)
        conn = _PostgresConnection(raw_connection)
        try:
            yield conn
            raw_connection.commit()
        except Exception:
            raw_connection.rollback()
            raise
        finally:
            raw_connection.close()
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(db_path: Path = DATABASE_PATH) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            biological_sex TEXT NOT NULL,
            height_cm REAL NOT NULL,
            weight_kg REAL NOT NULL,
            activity TEXT NOT NULL,
            goal TEXT NOT NULL,
            cuisine TEXT NOT NULL,
            conditions_json TEXT NOT NULL DEFAULT '[]',
            allergies_json TEXT NOT NULL DEFAULT '[]',
            medications TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lab_reports (
            id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            values_json TEXT NOT NULL,
            safety_level TEXT NOT NULL,
            created_at TEXT NOT NULL,
            profile_id TEXT NOT NULL DEFAULT '',
            reviewed_by TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS diet_plans (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            lab_report_id TEXT,
            name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            status TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(profile_id) REFERENCES profiles(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS food_logs (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            log_date TEXT NOT NULL,
            meal TEXT NOT NULL,
            food_name TEXT NOT NULL,
            servings REAL NOT NULL,
            calories REAL NOT NULL,
            protein_g REAL NOT NULL,
            carbs_g REAL NOT NULL,
            fat_g REAL NOT NULL,
            fiber_g REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(profile_id) REFERENCES profiles(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS measurements (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            measured_on TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            waist_cm REAL,
            water_l REAL,
            adherence_pct REAL,
            FOREIGN KEY(profile_id) REFERENCES profiles(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS care_reviews (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            reviewer_role TEXT NOT NULL DEFAULT 'Dietitian',
            FOREIGN KEY(plan_id) REFERENCES diet_plans(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            signature TEXT NOT NULL,
            severity TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            action TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            acknowledged_at TEXT,
            UNIQUE(profile_id, signature)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Customer', 'Dietitian')),
            display_name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            credential TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_login_at TEXT,
            approval_status TEXT NOT NULL DEFAULT 'Approved',
            approved_by TEXT,
            approved_at TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0,
            email_verified_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS email_otp_rate_limits (
            user_id TEXT PRIMARY KEY,
            last_sent_at TEXT NOT NULL,
            window_started_at TEXT NOT NULL,
            send_count INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS dietitian_customer_links (
            dietitian_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL,
            PRIMARY KEY(dietitian_id, customer_id),
            FOREIGN KEY(dietitian_id) REFERENCES users(id),
            FOREIGN KEY(customer_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS user_presence (
            user_id TEXT PRIMARY KEY,
            last_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS clinical_questionnaires (
            id TEXT PRIMARY KEY,
            dietitian_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            title TEXT NOT NULL,
            questions_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(dietitian_id) REFERENCES users(id),
            FOREIGN KEY(customer_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS questionnaire_answers (
            id TEXT PRIMARY KEY,
            questionnaire_id TEXT NOT NULL UNIQUE,
            customer_id TEXT NOT NULL,
            answers_json TEXT NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY(questionnaire_id) REFERENCES clinical_questionnaires(id),
            FOREIGN KEY(customer_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS clinical_messages (
            id TEXT PRIMARY KEY,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT,
            message_type TEXT NOT NULL DEFAULT 'Message',
            status TEXT NOT NULL DEFAULT 'Open',
            parent_id TEXT,
            FOREIGN KEY(sender_id) REFERENCES users(id),
            FOREIGN KEY(recipient_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS meal_schedule (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            day_name TEXT NOT NULL,
            meal_index INTEGER NOT NULL,
            scheduled_time TEXT NOT NULL,
            meal_name TEXT NOT NULL,
            meal_detail TEXT NOT NULL,
            calories REAL NOT NULL DEFAULT 0,
            protein_g REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Planned',
            completed_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(plan_id, scheduled_date, meal_index),
            FOREIGN KEY(profile_id) REFERENCES profiles(id),
            FOREIGN KEY(plan_id) REFERENCES diet_plans(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS clinical_notes (
            id TEXT PRIMARY KEY,
            dietitian_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dietitian_id) REFERENCES users(id),
            FOREIGN KEY(customer_id) REFERENCES users(id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS clinical_prescriptions (
            id TEXT PRIMARY KEY,
            dietitian_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            instructions TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL,
            FOREIGN KEY(dietitian_id) REFERENCES users(id),
            FOREIGN KEY(customer_id) REFERENCES users(id)
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx
        ON users (LOWER(username))
        """,
    ]
    with connection(db_path) as conn:
        for statement in statements:
            conn.execute(statement)
        migrations = {
            "users": {
                "approval_status": "TEXT NOT NULL DEFAULT 'Approved'",
                "approved_by": "TEXT",
                "approved_at": "TEXT",
                "is_admin": "INTEGER NOT NULL DEFAULT 0",
                "email_verified_at": "TEXT",
            },
            "lab_reports": {
                "profile_id": "TEXT NOT NULL DEFAULT ''",
                "reviewed_by": "TEXT NOT NULL DEFAULT ''",
            },
            "care_reviews": {
                "reviewer_role": "TEXT NOT NULL DEFAULT 'Dietitian'",
            },
            "clinical_messages": {
                "message_type": "TEXT NOT NULL DEFAULT 'Message'",
                "status": "TEXT NOT NULL DEFAULT 'Open'",
                "parent_id": "TEXT",
            },
        }
        for table_name, additions in migrations.items():
            if _uses_postgres(db_path):
                present = {
                    str(row["name"])
                    for row in conn.execute(
                        """SELECT column_name AS name
                           FROM information_schema.columns
                           WHERE table_schema = current_schema() AND table_name = ?""",
                        (table_name,),
                    )
                }
            else:
                present = {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table_name})")}
            for column_name, definition in additions.items():
                if column_name not in present:
                    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
                    if table_name == "users" and column_name == "email_verified_at":
                        # Accounts created before sign-up verification existed have already
                        # been in active use. Preserve their access during this one-time migration.
                        conn.execute(
                            "UPDATE users SET email_verified_at = created_at "
                            "WHERE email_verified_at IS NULL"
                        )


def upsert_profile(profile: dict[str, Any], db_path: Path = DATABASE_PATH) -> str:
    profile_id = str(profile.get("id") or "default-profile")
    payload = (
        profile_id, str(profile["name"]), int(profile["age"]),
        str(profile["biological_sex"]), float(profile["height_cm"]),
        float(profile["weight_kg"]), str(profile["activity"]),
        str(profile["goal"]), str(profile["cuisine"]),
        json.dumps(profile.get("conditions", [])),
        json.dumps(profile.get("allergies", [])),
        str(profile.get("medications", "")), utc_now(),
    )
    with connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, age=excluded.age,
                biological_sex=excluded.biological_sex,
                height_cm=excluded.height_cm, weight_kg=excluded.weight_kg,
                activity=excluded.activity, goal=excluded.goal,
                cuisine=excluded.cuisine,
                conditions_json=excluded.conditions_json,
                allergies_json=excluded.allergies_json,
                medications=excluded.medications,
                updated_at=excluded.updated_at
            """,
            payload,
        )
    return profile_id


def load_profile(profile_id: str = "default-profile", db_path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        return None
    profile = dict(row)
    profile["conditions"] = json.loads(profile.pop("conditions_json"))
    profile["allergies"] = json.loads(profile.pop("allergies_json"))
    return profile


def save_lab_report(file_name: str, values: list[dict[str, Any]], safety_level: str,
                    db_path: Path = DATABASE_PATH, *, profile_id: str = "",
                    reviewed_by: str = "") -> str:
    report_id = str(uuid.uuid4())
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO lab_reports
               (id, file_name, values_json, safety_level, created_at, profile_id, reviewed_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (report_id, file_name, json.dumps(values), safety_level, utc_now(), profile_id, reviewed_by),
        )
    return report_id


def list_lab_reports(profile_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM lab_reports WHERE profile_id = ? ORDER BY created_at DESC",
            (str(profile_id),),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["values"] = json.loads(item.pop("values_json"))
        result.append(item)
    return result


def save_plan(profile_id: str, plan: dict[str, Any], lab_report_id: str | None = None, db_path: Path = DATABASE_PATH) -> str:
    plan_id = str(uuid.uuid4())
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO diet_plans VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_id, profile_id, lab_report_id, plan["title"], int(plan["calories"]),
             plan["status"], json.dumps(plan), utc_now()),
        )
    return plan_id


def list_plans(profile_id: str = "default-profile", db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM diet_plans WHERE profile_id = ? ORDER BY created_at DESC",
            (profile_id,),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["plan"] = json.loads(item.pop("plan_json"))
        result.append(item)
    return result


def add_measurement(profile_id: str, measured_on: str, weight_kg: float, waist_cm: float | None,
                    water_l: float | None, adherence_pct: float | None,
                    db_path: Path = DATABASE_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO measurements VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), profile_id, measured_on, weight_kg, waist_cm, water_l, adherence_pct),
        )


def get_measurements(profile_id: str = "default-profile", db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM measurements WHERE profile_id = ? ORDER BY measured_on",
            (profile_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_food_log(profile_id: str, log_date: str, meal: str, food: dict[str, Any], servings: float,
                 db_path: Path = DATABASE_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO food_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid.uuid4()), profile_id, log_date, meal, str(food["food_name"]), servings,
                float(food.get("calories", 0)) * servings,
                float(food.get("protein_g", 0)) * servings,
                float(food.get("carbs_g", 0)) * servings,
                float(food.get("fat_g", 0)) * servings,
                float(food.get("fiber_g", 0)) * servings,
                utc_now(),
            ),
        )


def get_food_logs(profile_id: str = "default-profile", log_date: str | None = None,
                  db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    sql = "SELECT * FROM food_logs WHERE profile_id = ?"
    parameters: list[Any] = [profile_id]
    if log_date:
        sql += " AND log_date = ?"
        parameters.append(log_date)
    sql += " ORDER BY created_at DESC"
    with connection(db_path) as conn:
        rows = conn.execute(sql, tuple(parameters)).fetchall()
    return [dict(row) for row in rows]


def delete_food_log(log_id: str, profile_id: str = "default-profile",
                    db_path: Path = DATABASE_PATH) -> bool:
    with connection(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM food_logs WHERE id = ? AND profile_id = ?",
            (str(log_id), str(profile_id)),
        )
    return cursor.rowcount > 0


def request_review(plan_id: str, reviewer: str, note: str, db_path: Path = DATABASE_PATH,
                   *, reviewer_role: str = "Dietitian", status: str = "Reviewed") -> str:
    review_id = str(uuid.uuid4())
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO care_reviews
               (id, plan_id, reviewer, status, note, updated_at, reviewer_role)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (review_id, plan_id, reviewer, status, note, utc_now(), reviewer_role),
        )
    return review_id


def list_reviews(profile_id: str | None = None, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    where_clause = "WHERE diet_plans.profile_id = ?" if profile_id else ""
    parameters: tuple[Any, ...] = (str(profile_id),) if profile_id else ()
    with connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT care_reviews.*, diet_plans.name AS plan_name
            FROM care_reviews
            JOIN diet_plans ON diet_plans.id = care_reviews.plan_id
            {where_clause}
            ORDER BY care_reviews.updated_at DESC
            """,
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]


def sync_alerts(alerts: list[dict[str, Any]], profile_id: str = "default-profile",
                db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    """Persist the latest rule-engine state while retaining acknowledgements."""
    now = utc_now()
    signatures = [str(alert["signature"]) for alert in alerts]
    with connection(db_path) as conn:
        existing_rows = conn.execute(
            "SELECT * FROM alerts WHERE profile_id = ?", (profile_id,),
        ).fetchall()
        existing = {str(row["signature"]): dict(row) for row in existing_rows}
        for alert in alerts:
            signature = str(alert["signature"])
            previous = existing.get(signature)
            alert_id = str(previous["id"]) if previous else str(uuid.uuid4())
            created_at = str(previous["created_at"]) if previous else now
            acknowledged_at = previous.get("acknowledged_at") if previous else None
            status_value = "Acknowledged" if previous and previous.get("status") == "Acknowledged" else "Active"
            conn.execute(
                """
                INSERT INTO alerts (
                    id, profile_id, signature, severity, category, title,
                    message, action, source, status, created_at, updated_at, acknowledged_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id, signature) DO UPDATE SET
                    severity=excluded.severity,
                    category=excluded.category,
                    title=excluded.title,
                    message=excluded.message,
                    action=excluded.action,
                    source=excluded.source,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    acknowledged_at=excluded.acknowledged_at
                """,
                (
                    alert_id, profile_id, signature, str(alert["severity"]),
                    str(alert["category"]), str(alert["title"]), str(alert["message"]),
                    str(alert["action"]), str(alert["source"]), status_value,
                    created_at, now, acknowledged_at,
                ),
            )
        if signatures:
            placeholders = ",".join("?" for _ in signatures)
            conn.execute(
                f"""UPDATE alerts SET status = 'Resolved', updated_at = ?
                    WHERE profile_id = ? AND signature NOT IN ({placeholders})
                    AND status != 'Resolved'""",
                (now, profile_id, *signatures),
            )
        else:
            conn.execute(
                """UPDATE alerts SET status = 'Resolved', updated_at = ?
                    WHERE profile_id = ? AND status != 'Resolved'""",
                (now, profile_id),
            )
    return list_alerts(profile_id=profile_id, include_resolved=False, db_path=db_path)


def list_alerts(profile_id: str = "default-profile", *, status: str | None = None,
                include_resolved: bool = False,
                db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    sql = "SELECT * FROM alerts WHERE profile_id = ?"
    parameters: list[Any] = [profile_id]
    if status:
        sql += " AND status = ?"
        parameters.append(status)
    elif not include_resolved:
        sql += " AND status != 'Resolved'"
    sql += """ ORDER BY CASE severity
        WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
        updated_at DESC"""
    with connection(db_path) as conn:
        rows = conn.execute(sql, tuple(parameters)).fetchall()
    return [dict(row) for row in rows]


def acknowledge_alert(alert_id: str, profile_id: str = "default-profile",
                      db_path: Path = DATABASE_PATH) -> bool:
    now = utc_now()
    with connection(db_path) as conn:
        cursor = conn.execute(
            """UPDATE alerts SET status = 'Acknowledged', acknowledged_at = ?, updated_at = ?
               WHERE id = ? AND profile_id = ? AND status = 'Active'""",
            (now, now, str(alert_id), profile_id),
        )
    return cursor.rowcount > 0


def acknowledge_all_alerts(profile_id: str = "default-profile",
                           db_path: Path = DATABASE_PATH) -> int:
    now = utc_now()
    with connection(db_path) as conn:
        cursor = conn.execute(
            """UPDATE alerts SET status = 'Acknowledged', acknowledged_at = ?, updated_at = ?
               WHERE profile_id = ? AND status = 'Active'""",
            (now, now, profile_id),
        )
    return int(cursor.rowcount)


def create_user(username: str, password_hash: str, role: str, display_name: str,
                email: str = "", credential: str = "",
                db_path: Path = DATABASE_PATH, *, approval_status: str | None = None,
                is_admin: bool = False, email_verified: bool = True) -> dict[str, Any]:
    user_id = str(uuid.uuid4())
    approval = approval_status or ("Pending" if role == "Dietitian" else "Approved")
    active = int(email_verified and (approval == "Approved" or is_admin))
    approved_at = utc_now() if active else None
    email_verified_at = utc_now() if email_verified else None
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO users
               (id, username, password_hash, role, display_name, email, credential, active,
                created_at, approval_status, approved_by, approved_at, is_admin,
                email_verified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
            (user_id, username.strip(), password_hash, role, display_name.strip(),
             email.strip().lower(), credential.strip(), active, utc_now(), approval,
             approved_at, int(is_admin), email_verified_at),
        )
    return get_user(user_id, db_path=db_path) or {}


def get_user(user_id: str, db_path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username: str, db_path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    with connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),),
        ).fetchone()
    return dict(row) if row else None


def record_login(user_id: str, db_path: Path = DATABASE_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (utc_now(), str(user_id)))


def presence_ttl_seconds() -> int:
    """Return the configured live-presence window with safe operational bounds."""
    try:
        configured = int(os.getenv("NUTRIPULSE_PRESENCE_TTL_SECONDS", "300") or 300)
    except ValueError:
        configured = 300
    return min(1800, max(60, configured))


def touch_dietitian_presence(
    user_id: str, db_path: Path = DATABASE_PATH, *, seen_at: datetime | None = None,
) -> bool:
    """Record a heartbeat only for an active, approved Dietitian account."""
    moment = seen_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    timestamp = moment.astimezone(timezone.utc).isoformat(timespec="seconds")
    with connection(db_path) as conn:
        user = conn.execute(
            """SELECT role, active, approval_status FROM users WHERE id = ?""",
            (str(user_id),),
        ).fetchone()
        if (
            not user
            or str(user["role"]) != "Dietitian"
            or not int(user["active"])
            or str(user["approval_status"]) != "Approved"
        ):
            return False
        conn.execute(
            """INSERT INTO user_presence (user_id, last_seen_at, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   last_seen_at=excluded.last_seen_at,
                   updated_at=excluded.updated_at""",
            (str(user_id), timestamp, timestamp),
        )
    return True


def clear_user_presence(user_id: str, db_path: Path = DATABASE_PATH) -> bool:
    """Remove presence immediately on explicit sign-out; TTL handles closed tabs."""
    with connection(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM user_presence WHERE user_id = ?", (str(user_id),),
        )
    return cursor.rowcount > 0


def list_live_dietitians_for_customer(
    customer_id: str, db_path: Path = DATABASE_PATH, *,
    now: datetime | None = None, ttl_seconds: int | None = None,
) -> list[dict[str, Any]]:
    """Return live Dietitians linked to one customer, never another caseload."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    ttl = presence_ttl_seconds() if ttl_seconds is None else max(1, int(ttl_seconds))
    cutoff = current - timedelta(seconds=ttl)
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT users.id, users.username, users.display_name, users.email,
                      users.credential, user_presence.last_seen_at
               FROM dietitian_customer_links
               JOIN users ON users.id = dietitian_customer_links.dietitian_id
               JOIN user_presence ON user_presence.user_id = users.id
               WHERE dietitian_customer_links.customer_id = ?
                 AND dietitian_customer_links.status = 'Active'
                 AND users.role = 'Dietitian'
                 AND users.active = 1
                 AND users.approval_status = 'Approved'
               ORDER BY LOWER(users.display_name)""",
            (str(customer_id),),
        ).fetchall()
    live: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            last_seen = datetime.fromisoformat(str(item["last_seen_at"]).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        if last_seen.astimezone(timezone.utc) < cutoff:
            continue
        item["is_live"] = True
        item["seconds_since_seen"] = max(0, int((current - last_seen.astimezone(timezone.utc)).total_seconds()))
        live.append(item)
    return live


def update_user_password(user_id: str, password_hash: str,
                         db_path: Path = DATABASE_PATH) -> bool:
    """Replace an account password only after the caller verifies account ownership."""
    if not str(password_hash or "").startswith("pbkdf2_sha256$"):
        raise ValueError("A valid PBKDF2 password hash is required.")
    with connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ? AND active = 1",
            (str(password_hash), str(user_id)),
        )
    return cursor.rowcount > 0


def set_verified_user_email(user_id: str, email: str, db_path: Path = DATABASE_PATH) -> bool:
    """Store an email and verification timestamp after a successful sign-up code."""
    clean_email = str(email or "").strip().lower()
    if not clean_email:
        raise ValueError("A verified email address is required.")
    with connection(db_path) as conn:
        verified_at = utc_now()
        cursor = conn.execute(
            """UPDATE users
               SET email = ?, email_verified_at = ?,
                   active = CASE WHEN role = 'Customer' OR is_admin = 1 THEN 1 ELSE active END,
                   approved_at = CASE
                       WHEN (role = 'Customer' OR is_admin = 1) AND approved_at IS NULL THEN ?
                       ELSE approved_at
                   END
               WHERE id = ?""",
            (clean_email, verified_at, verified_at, str(user_id)),
        )
    return cursor.rowcount > 0


def reserve_email_otp_delivery(
    user_id: str, db_path: Path = DATABASE_PATH, *, now: datetime | None = None,
) -> tuple[bool, int]:
    """Reserve one OTP delivery with a 60-second cooldown and ten-per-hour cap."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    with connection(db_path) as conn:
        row = conn.execute(
            "SELECT last_sent_at, window_started_at, send_count FROM email_otp_rate_limits WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
        if row:
            last_sent = datetime.fromisoformat(str(row["last_sent_at"]))
            window_started = datetime.fromisoformat(str(row["window_started_at"]))
            seconds_since_last = (current - last_sent).total_seconds()
            if seconds_since_last < 60:
                return False, max(1, int(60 - seconds_since_last + 0.999))
            window_age = (current - window_started).total_seconds()
            if window_age < 3600 and int(row["send_count"]) >= 10:
                return False, max(1, int(3600 - window_age + 0.999))
            if window_age >= 3600:
                window_started = current
                send_count = 1
            else:
                send_count = int(row["send_count"]) + 1
            conn.execute(
                """UPDATE email_otp_rate_limits
                   SET last_sent_at = ?, window_started_at = ?, send_count = ?
                   WHERE user_id = ?""",
                (current.isoformat(), window_started.isoformat(), send_count, str(user_id)),
            )
        else:
            conn.execute(
                """INSERT INTO email_otp_rate_limits
                   (user_id, last_sent_at, window_started_at, send_count)
                   VALUES (?, ?, ?, 1)""",
                (str(user_id), current.isoformat(), current.isoformat()),
            )
    return True, 0


def list_users(role: str | None = None, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    sql = """SELECT id, username, role, display_name, email, credential, active,
                    created_at, last_login_at, approval_status, approved_by, approved_at, is_admin
             FROM users"""
    parameters: tuple[Any, ...] = ()
    if role:
        sql += " WHERE role = ?"
        parameters = (role,)
    sql += " ORDER BY LOWER(display_name)"
    with connection(db_path) as conn:
        rows = conn.execute(sql, parameters).fetchall()
    return [dict(row) for row in rows]


def has_admin(db_path: Path = DATABASE_PATH) -> bool:
    with connection(db_path) as conn:
        row = conn.execute("SELECT 1 FROM users WHERE is_admin = 1 LIMIT 1").fetchone()
    return bool(row)


def set_dietitian_approval(user_id: str, admin_id: str, approved: bool,
                           db_path: Path = DATABASE_PATH) -> bool:
    status = "Approved" if approved else "Rejected"
    with connection(db_path) as conn:
        admin = conn.execute(
            "SELECT is_admin, active FROM users WHERE id = ?", (str(admin_id),),
        ).fetchone()
        target = conn.execute(
            "SELECT role FROM users WHERE id = ?", (str(user_id),),
        ).fetchone()
        if not admin or not int(admin["is_admin"]) or not int(admin["active"]):
            raise PermissionError("Administrator approval is required.")
        if not target or str(target["role"]) != "Dietitian":
            raise ValueError("Only Dietitian applications can be approved here.")
        cursor = conn.execute(
            """UPDATE users SET approval_status = ?, active = ?, approved_by = ?, approved_at = ?
               WHERE id = ?""",
            (status, int(approved), str(admin_id), utc_now(), str(user_id)),
        )
    return cursor.rowcount > 0


def link_dietitian_customer(dietitian_id: str, customer_id: str,
                            db_path: Path = DATABASE_PATH) -> None:
    with connection(db_path) as conn:
        roles = conn.execute(
            "SELECT id, role FROM users WHERE id IN (?, ?)", (dietitian_id, customer_id),
        ).fetchall()
        role_map = {str(row["id"]): str(row["role"]) for row in roles}
        if role_map.get(dietitian_id) != "Dietitian" or role_map.get(customer_id) != "Customer":
            raise ValueError("A care link requires one registered Dietitian and one Customer.")
        conn.execute(
            """INSERT INTO dietitian_customer_links VALUES (?, ?, 'Active', ?)
               ON CONFLICT(dietitian_id, customer_id) DO UPDATE SET status='Active'""",
            (dietitian_id, customer_id, utc_now()),
        )


def set_caseload_assignment(dietitian_id: str, customer_id: str, active: bool,
                            db_path: Path = DATABASE_PATH) -> None:
    if active:
        link_dietitian_customer(dietitian_id, customer_id, db_path)
        return
    with connection(db_path) as conn:
        conn.execute(
            """UPDATE dietitian_customer_links SET status = 'Inactive'
               WHERE dietitian_id = ? AND customer_id = ?""",
            (str(dietitian_id), str(customer_id)),
        )


def list_caseload_links(db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT links.dietitian_id, links.customer_id, links.status, links.created_at,
                      dietitian.display_name AS dietitian_name,
                      customer.display_name AS customer_name
               FROM dietitian_customer_links links
               JOIN users dietitian ON dietitian.id = links.dietitian_id
               JOIN users customer ON customer.id = links.customer_id
               ORDER BY LOWER(dietitian.display_name),
                        LOWER(customer.display_name)"""
        ).fetchall()
    return [dict(row) for row in rows]


def list_linked_customers(dietitian_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT users.id, users.username, users.display_name, users.email,
                      dietitian_customer_links.status, dietitian_customer_links.created_at
               FROM dietitian_customer_links JOIN users ON users.id = dietitian_customer_links.customer_id
               WHERE dietitian_customer_links.dietitian_id = ? AND dietitian_customer_links.status = 'Active'
                     AND users.active = 1
               ORDER BY LOWER(users.display_name)""",
            (dietitian_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_linked_dietitians(customer_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT users.id, users.username, users.display_name, users.email, users.credential,
                      dietitian_customer_links.status, dietitian_customer_links.created_at
               FROM dietitian_customer_links JOIN users ON users.id = dietitian_customer_links.dietitian_id
               WHERE dietitian_customer_links.customer_id = ? AND dietitian_customer_links.status = 'Active'
                     AND users.active = 1 AND users.approval_status = 'Approved'
               ORDER BY LOWER(users.display_name)""",
            (customer_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def create_questionnaire(dietitian_id: str, customer_id: str, title: str,
                         questions: list[str], db_path: Path = DATABASE_PATH) -> str:
    questionnaire_id = str(uuid.uuid4())
    clean_questions = [str(item).strip() for item in questions if str(item).strip()]
    if not clean_questions:
        raise ValueError("Add at least one clinical question.")
    with connection(db_path) as conn:
        link = conn.execute(
            """SELECT 1 FROM dietitian_customer_links
               WHERE dietitian_id = ? AND customer_id = ? AND status = 'Active'""",
            (dietitian_id, customer_id),
        ).fetchone()
        if not link:
            raise ValueError("The customer is not linked to this dietitian.")
        conn.execute(
            "INSERT INTO clinical_questionnaires VALUES (?, ?, ?, ?, ?, 'Open', ?, NULL)",
            (questionnaire_id, dietitian_id, customer_id, title.strip(), json.dumps(clean_questions), utc_now()),
        )
    return questionnaire_id


def list_questionnaires(*, customer_id: str | None = None, dietitian_id: str | None = None,
                        db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    sql = """SELECT clinical_questionnaires.*, u1.display_name AS dietitian_name,
                    u2.display_name AS customer_name, questionnaire_answers.answers_json,
                    questionnaire_answers.submitted_at
             FROM clinical_questionnaires
             JOIN users u1 ON u1.id = clinical_questionnaires.dietitian_id
             JOIN users u2 ON u2.id = clinical_questionnaires.customer_id
             LEFT JOIN questionnaire_answers ON questionnaire_answers.questionnaire_id = clinical_questionnaires.id
             WHERE 1=1"""
    parameters: list[Any] = []
    if customer_id:
        sql += " AND clinical_questionnaires.customer_id = ?"
        parameters.append(customer_id)
    if dietitian_id:
        sql += " AND clinical_questionnaires.dietitian_id = ?"
        parameters.append(dietitian_id)
    sql += " ORDER BY clinical_questionnaires.created_at DESC"
    with connection(db_path) as conn:
        rows = conn.execute(sql, tuple(parameters)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["questions"] = json.loads(item.pop("questions_json"))
        raw_answers = item.pop("answers_json", None)
        item["answers"] = json.loads(raw_answers) if raw_answers else None
        result.append(item)
    return result


def submit_questionnaire(questionnaire_id: str, customer_id: str, answers: dict[str, str],
                         db_path: Path = DATABASE_PATH) -> None:
    now = utc_now()
    with connection(db_path) as conn:
        questionnaire = conn.execute(
            "SELECT customer_id, status FROM clinical_questionnaires WHERE id = ?", (questionnaire_id,),
        ).fetchone()
        if not questionnaire or str(questionnaire["customer_id"]) != customer_id:
            raise ValueError("Questionnaire not found for this customer.")
        conn.execute(
            """INSERT INTO questionnaire_answers VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(questionnaire_id) DO UPDATE SET answers_json=excluded.answers_json,
               customer_id=excluded.customer_id, submitted_at=excluded.submitted_at""",
            (str(uuid.uuid4()), questionnaire_id, customer_id, json.dumps(answers), now),
        )
        conn.execute(
            "UPDATE clinical_questionnaires SET status='Completed', completed_at=? WHERE id=?",
            (now, questionnaire_id),
        )


def add_clinical_note(dietitian_id: str, customer_id: str, note: str,
                      db_path: Path = DATABASE_PATH) -> str:
    clean_note = note.strip()
    if len(clean_note) < 3:
        raise ValueError("Clinical note cannot be empty.")
    note_id = str(uuid.uuid4())
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO clinical_notes VALUES (?, ?, ?, ?, ?)",
            (note_id, str(dietitian_id), str(customer_id), clean_note, utc_now()),
        )
    return note_id


def list_clinical_notes(customer_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT clinical_notes.*, users.display_name AS dietitian_name
               FROM clinical_notes JOIN users ON users.id = clinical_notes.dietitian_id
               WHERE customer_id = ? ORDER BY created_at DESC""",
            (str(customer_id),),
        ).fetchall()
    return [dict(row) for row in rows]


def add_clinical_prescription(dietitian_id: str, customer_id: str, category: str,
                              title: str, instructions: str,
                              db_path: Path = DATABASE_PATH) -> str:
    if len(title.strip()) < 2 or len(instructions.strip()) < 3:
        raise ValueError("Add a title and clear nutrition instructions.")
    prescription_id = str(uuid.uuid4())
    with connection(db_path) as conn:
        conn.execute(
            """INSERT INTO clinical_prescriptions
               (id, dietitian_id, customer_id, category, title, instructions, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'Active', ?)""",
            (prescription_id, str(dietitian_id), str(customer_id), category.strip(),
             title.strip(), instructions.strip(), utc_now()),
        )
    return prescription_id


def list_clinical_prescriptions(customer_id: str,
                                db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            """SELECT clinical_prescriptions.*, users.display_name AS dietitian_name,
                      users.credential AS dietitian_credential
               FROM clinical_prescriptions JOIN users ON users.id = clinical_prescriptions.dietitian_id
               WHERE customer_id = ? ORDER BY created_at DESC""",
            (str(customer_id),),
        ).fetchall()
    return [dict(row) for row in rows]


def set_prescription_status(prescription_id: str, customer_id: str, status: str,
                            db_path: Path = DATABASE_PATH) -> bool:
    if status not in {"Active", "Completed", "Cancelled"}:
        raise ValueError("Unsupported prescription status.")
    with connection(db_path) as conn:
        cursor = conn.execute(
            "UPDATE clinical_prescriptions SET status = ? WHERE id = ? AND customer_id = ?",
            (status, str(prescription_id), str(customer_id)),
        )
    return cursor.rowcount > 0


def send_clinical_message(sender_id: str, recipient_id: str, subject: str, body: str,
                          db_path: Path = DATABASE_PATH, *, message_type: str = "Message",
                          parent_id: str | None = None) -> str:
    if message_type not in {"Message", "Question", "Recommendation", "Response"}:
        raise ValueError("Unsupported clinical message type.")
    if len(subject.strip()) < 2 or len(body.strip()) < 2:
        raise ValueError("Add a subject and message.")
    message_id = str(uuid.uuid4())
    with connection(db_path) as conn:
        linked = conn.execute(
            """SELECT 1 FROM dietitian_customer_links
               WHERE ((dietitian_id=? AND customer_id=?) OR (dietitian_id=? AND customer_id=?))
               AND status='Active'""",
            (sender_id, recipient_id, recipient_id, sender_id),
        ).fetchone()
        admin = conn.execute(
            "SELECT 1 FROM users WHERE id IN (?, ?) AND is_admin = 1 AND active = 1 LIMIT 1",
            (str(sender_id), str(recipient_id)),
        ).fetchone()
        if not linked and not admin:
            raise ValueError("Messages are limited to linked care-team accounts.")
        sender = conn.execute("SELECT role FROM users WHERE id = ?", (str(sender_id),)).fetchone()
        if sender and str(sender["role"]) == "Customer":
            question = conn.execute(
                """SELECT id FROM clinical_messages
                   WHERE sender_id = ? AND recipient_id = ? AND message_type = 'Question'
                         AND status = 'Open'
                   ORDER BY created_at DESC LIMIT 1""",
                (str(recipient_id), str(sender_id)),
            ).fetchone()
            if question:
                parent_id = parent_id or str(question["id"])
                conn.execute(
                    "UPDATE clinical_messages SET status = 'Answered' WHERE id = ?",
                    (str(question["id"]),),
                )
                message_type = "Response"
        message_status = "Open" if message_type == "Question" else "Sent"
        conn.execute(
            """INSERT INTO clinical_messages
               (id, sender_id, recipient_id, subject, body, created_at, read_at,
                message_type, status, parent_id)
               VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)""",
            (message_id, sender_id, recipient_id, subject.strip(), body.strip(), utc_now(),
             message_type, message_status, parent_id),
        )
    return message_id


def list_clinical_messages(user_id: str, other_user_id: str | None = None,
                           db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    sql = """SELECT clinical_messages.*, sender.display_name AS sender_name,
                    recipient.display_name AS recipient_name
             FROM clinical_messages
             JOIN users sender ON sender.id=clinical_messages.sender_id
             JOIN users recipient ON recipient.id=clinical_messages.recipient_id
             WHERE (sender_id=? OR recipient_id=?)"""
    parameters: list[Any] = [user_id, user_id]
    if other_user_id:
        sql += " AND (sender_id=? OR recipient_id=?)"
        parameters.extend([other_user_id, other_user_id])
    sql += " ORDER BY created_at"
    with connection(db_path) as conn:
        rows = conn.execute(sql, tuple(parameters)).fetchall()
        conn.execute(
            "UPDATE clinical_messages SET read_at=? WHERE recipient_id=? AND read_at IS NULL",
            (utc_now(), user_id),
        )
    return [dict(row) for row in rows]


def create_meal_schedule(profile_id: str, plan_id: str, plan: dict[str, Any],
                         week_start: str, db_path: Path = DATABASE_PATH) -> int:
    start = date_type.fromisoformat(week_start)
    created = 0
    with connection(db_path) as conn:
        for day_index, day in enumerate(plan.get("days", [])):
            scheduled_date = (start + timedelta(days=day_index)).isoformat()
            for meal_index, meal in enumerate(day.get("meals", [])):
                cursor = conn.execute(
                    """INSERT INTO meal_schedule
                       (id, profile_id, plan_id, scheduled_date, day_name, meal_index,
                        scheduled_time, meal_name, meal_detail, calories, protein_g,
                        status, completed_at, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Planned', NULL, ?)
                       ON CONFLICT(plan_id, scheduled_date, meal_index) DO NOTHING""",
                    (str(uuid.uuid4()), profile_id, plan_id, scheduled_date, str(day.get("day", "Day")),
                     meal_index, str(meal.get("time", "12:00")), str(meal.get("name", "Meal")),
                     str(meal.get("detail", "")), float(meal.get("calories", 0)),
                     float(meal.get("protein_g", 0)), utc_now()),
                )
                created += int(cursor.rowcount)
    return created


def list_meal_schedule(profile_id: str, *, date_from: str | None = None,
                       date_to: str | None = None, plan_id: str | None = None,
                       db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    sql = "SELECT * FROM meal_schedule WHERE profile_id = ?"
    parameters: list[Any] = [profile_id]
    if date_from:
        sql += " AND scheduled_date >= ?"
        parameters.append(date_from)
    if date_to:
        sql += " AND scheduled_date <= ?"
        parameters.append(date_to)
    if plan_id:
        sql += " AND plan_id = ?"
        parameters.append(plan_id)
    sql += " ORDER BY scheduled_date, scheduled_time, meal_index"
    with connection(db_path) as conn:
        rows = conn.execute(sql, tuple(parameters)).fetchall()
    return [dict(row) for row in rows]


def _summarize_schedule(rows: list[dict[str, Any]], plan_id: str | None) -> dict[str, Any]:
    if not rows:
        return {
            "plan_id": plan_id, "days": [], "weeks": [], "active_date": None,
            "active_week_number": 0, "completed_weeks": 0,
            "completed_meals": 0, "total_meals": 0, "completion_pct": 0.0,
        }
    first_date = min(date_type.fromisoformat(str(row["scheduled_date"])) for row in rows)
    by_day: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_day.setdefault(str(row["scheduled_date"]), []).append(row)
    days: list[dict[str, Any]] = []
    for scheduled_date in sorted(by_day):
        day_rows = by_day[scheduled_date]
        completed = sum(str(row.get("status")) == "Completed" for row in day_rows)
        skipped = sum(str(row.get("status")) == "Skipped" for row in day_rows)
        total = len(day_rows)
        day_date = date_type.fromisoformat(scheduled_date)
        week_number = ((day_date - first_date).days // 7) + 1
        if total and completed == total:
            state = "Completed"
        elif completed or skipped:
            state = "In progress"
        else:
            state = "Upcoming"
        days.append({
            "scheduled_date": scheduled_date,
            "day_name": str(day_rows[0].get("day_name", day_date.strftime("%A"))),
            "week_number": week_number,
            "completed": completed,
            "skipped": skipped,
            "total": total,
            "completion_pct": round(completed / total * 100, 1) if total else 0.0,
            "status": state,
        })
    weeks: list[dict[str, Any]] = []
    for week_number in sorted({int(day["week_number"]) for day in days}):
        week_days = [day for day in days if int(day["week_number"]) == week_number]
        completed = sum(int(day["completed"]) for day in week_days)
        skipped = sum(int(day["skipped"]) for day in week_days)
        total = sum(int(day["total"]) for day in week_days)
        if total and completed == total:
            state = "Completed"
        elif completed or skipped:
            state = "In progress"
        else:
            state = "Upcoming"
        weeks.append({
            "week_number": week_number,
            "week_start": str(week_days[0]["scheduled_date"]),
            "week_end": str(week_days[-1]["scheduled_date"]),
            "completed": completed,
            "skipped": skipped,
            "total": total,
            "completion_pct": round(completed / total * 100, 1) if total else 0.0,
            "status": state,
        })
    active_day = next((day for day in days if day["status"] != "Completed"), None)
    completed_meals = sum(int(day["completed"]) for day in days)
    total_meals = sum(int(day["total"]) for day in days)
    return {
        "plan_id": plan_id,
        "first_date": first_date.isoformat(),
        "days": days,
        "weeks": weeks,
        "active_date": active_day["scheduled_date"] if active_day else None,
        "active_week_number": int(active_day["week_number"]) if active_day else (len(weeks) + 1),
        "completed_weeks": sum(week["status"] == "Completed" for week in weeks),
        "completed_meals": completed_meals,
        "total_meals": total_meals,
        "completion_pct": round(completed_meals / total_meals * 100, 1) if total_meals else 0.0,
    }


def get_schedule_progress(profile_id: str, plan_id: str | None = None,
                          db_path: Path = DATABASE_PATH) -> dict[str, Any]:
    selected_plan_id = plan_id
    with connection(db_path) as conn:
        if not selected_plan_id:
            latest = conn.execute(
                """SELECT plan_id FROM meal_schedule WHERE profile_id=?
                   ORDER BY created_at DESC, scheduled_date DESC LIMIT 1""",
                (profile_id,),
            ).fetchone()
            selected_plan_id = str(latest["plan_id"]) if latest else None
        if not selected_plan_id:
            rows: list[dict[str, Any]] = []
        else:
            fetched = conn.execute(
                """SELECT * FROM meal_schedule WHERE profile_id=? AND plan_id=?
                   ORDER BY scheduled_date, scheduled_time, meal_index""",
                (profile_id, selected_plan_id),
            ).fetchall()
            rows = [dict(row) for row in fetched]
    return _summarize_schedule(rows, selected_plan_id)


def set_meal_status_with_progress(meal_id: str, profile_id: str, status: str,
                                  db_path: Path = DATABASE_PATH) -> dict[str, Any]:
    if status not in {"Planned", "Completed", "Skipped"}:
        raise ValueError("Meal status must be Planned, Completed, or Skipped.")
    completed_at = utc_now() if status == "Completed" else None
    with connection(db_path) as conn:
        meal = conn.execute(
            "SELECT * FROM meal_schedule WHERE id=? AND profile_id=?",
            (meal_id, profile_id),
        ).fetchone()
        if not meal:
            return {"updated": False, "meal_id": meal_id, "profile_id": profile_id, "status": status}
        cursor = conn.execute(
            "UPDATE meal_schedule SET status=?, completed_at=? WHERE id=? AND profile_id=?",
            (status, completed_at, meal_id, profile_id),
        )
        meal_row = dict(meal)
    plan_id = str(meal_row["plan_id"])
    progress = get_schedule_progress(profile_id, plan_id, db_path)
    day = next(
        (item for item in progress["days"] if item["scheduled_date"] == str(meal_row["scheduled_date"])),
        None,
    )
    week = next(
        (item for item in progress["weeks"] if day and item["week_number"] == day["week_number"]),
        None,
    )
    day_completed = bool(status == "Completed" and day and day["status"] == "Completed")
    completed_week_number = (
        int(week["week_number"])
        if day_completed and week and week["status"] == "Completed"
        else None
    )
    next_week_created = False
    if completed_week_number is not None:
        next_week_start = date_type.fromisoformat(str(progress["first_date"])) + timedelta(days=completed_week_number * 7)
        with connection(db_path) as conn:
            plan_row = conn.execute(
                "SELECT plan_json FROM diet_plans WHERE id=? AND profile_id=?",
                (plan_id, profile_id),
            ).fetchone()
        if plan_row:
            created = create_meal_schedule(
                profile_id, plan_id, json.loads(str(plan_row["plan_json"])),
                next_week_start.isoformat(), db_path,
            )
            next_week_created = created > 0
            progress = get_schedule_progress(profile_id, plan_id, db_path)
    return {
        "updated": cursor.rowcount > 0,
        "meal_id": meal_id,
        "profile_id": profile_id,
        "plan_id": plan_id,
        "status": status,
        "scheduled_date": str(meal_row["scheduled_date"]),
        "day_completed": day_completed,
        "completed_week_number": completed_week_number,
        "next_week_created": next_week_created,
        "next_active_date": progress.get("active_date"),
        "progress": progress,
    }


def set_meal_status(meal_id: str, profile_id: str, status: str,
                    db_path: Path = DATABASE_PATH) -> bool:
    return bool(set_meal_status_with_progress(meal_id, profile_id, status, db_path).get("updated"))
