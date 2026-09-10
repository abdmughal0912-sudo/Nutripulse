"""Persistent sign-in limits and revocable server-side account sessions."""
from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

from .constants import DATABASE_PATH
from .database import connection, get_user, utc_now

LOGIN_WINDOW_SECONDS = 900
LOGIN_MAX_ATTEMPTS = 8
SESSION_IDLE_SECONDS = 3600
SESSION_MAX_SECONDS = 43200


def reserve_login_attempt(identity: str, db_path: Path = DATABASE_PATH, *, now: float | None = None) -> bool:
    current = time.time() if now is None else now
    bucket = hashlib.sha256(identity.strip().lower().encode()).hexdigest()
    cutoff = current - LOGIN_WINDOW_SECONDS
    with connection(db_path) as conn:
        conn.execute("DELETE FROM login_attempts WHERE window_started < ?", (current - 86400,))
        row = conn.execute(
            """INSERT INTO login_attempts(bucket, attempts, window_started) VALUES (?, 1, ?)
            ON CONFLICT(bucket) DO UPDATE SET
              attempts = CASE WHEN login_attempts.window_started <= ? THEN 1 ELSE login_attempts.attempts + 1 END,
              window_started = CASE WHEN login_attempts.window_started <= ? THEN ? ELSE login_attempts.window_started END
            WHERE login_attempts.attempts < ? OR login_attempts.window_started <= ?
            RETURNING attempts""",
            (bucket, current, cutoff, cutoff, current, LOGIN_MAX_ATTEMPTS, cutoff),
        ).fetchone()
    return row is not None


def clear_login_attempts(identity: str, db_path: Path = DATABASE_PATH) -> None:
    bucket = hashlib.sha256(identity.strip().lower().encode()).hexdigest()
    with connection(db_path) as conn:
        conn.execute("DELETE FROM login_attempts WHERE bucket = ?", (bucket,))


def record_account_event(user_id: str, action: str, db_path: Path = DATABASE_PATH) -> None:
    if action not in {"Signed in", "Incorrect password", "Signed out", "All sessions revoked"}:
        raise ValueError("Unsupported account event.")
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO account_events(id, user_id, action, created_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, action, utc_now()),
        )


def validate_account_session(snapshot: dict[str, Any], *, started_at: float, last_active_at: float,
                             now: float | None = None, db_path: Path = DATABASE_PATH) -> dict[str, Any] | None:
    current = time.time() if now is None else now
    if not (0 <= current - started_at < SESSION_MAX_SECONDS and
            0 <= current - last_active_at < SESSION_IDLE_SECONDS):
        return None
    user = get_user(str(snapshot.get("id", "")), db_path)
    if not user or not user.get("active") or not user.get("email_verified_at"):
        return None
    if user.get("approval_status") != "Approved":
        return None
    if (int(user.get("session_version", 0)) != int(snapshot.get("session_version", 0)) or
            user["role"] != snapshot.get("role") or
            bool(user.get("is_admin")) != bool(snapshot.get("is_admin"))):
        return None
    return {key: value for key, value in user.items() if key != "password_hash"}


def revoke_account_sessions(user_id: str, db_path: Path = DATABASE_PATH) -> None:
    with connection(db_path) as conn:
        conn.execute("UPDATE users SET session_version = session_version + 1 WHERE id = ?", (user_id,))
        conn.execute("UPDATE user_presence SET last_seen_at = '' WHERE user_id = ?", (user_id,))
        conn.execute(
            "INSERT INTO account_events(id, user_id, action, created_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), user_id, "All sessions revoked", utc_now()),
        )


def list_account_events(user_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT action, created_at FROM account_events WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]
