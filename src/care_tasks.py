"""Caseload-scoped care tasks and explicit message read receipts."""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any

from .constants import DATABASE_PATH
from .database import connection, utc_now
from .local_time import local_today

TASK_STATUSES = ("Open", "In progress", "Completed", "Cancelled")
TASK_PRIORITIES = ("Normal", "High")


def _active_user(conn: Any, user_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row or not row["active"] or row["approval_status"] != "Approved" or not row["email_verified_at"]:
        raise PermissionError("An active, approved account is required.")
    return dict(row)


def _authorize_customer(conn: Any, actor: dict[str, Any], customer_id: str) -> None:
    customer = conn.execute("SELECT role FROM users WHERE id = ?", (customer_id,)).fetchone()
    if not customer or customer["role"] != "Customer":
        raise PermissionError("Select a customer account.")
    if actor["is_admin"] or (actor["role"] == "Customer" and actor["id"] == customer_id):
        return
    if actor["role"] == "Dietitian" and conn.execute(
        "SELECT 1 FROM dietitian_customer_links WHERE dietitian_id = ? AND customer_id = ? AND status = 'Active'",
        (actor["id"], customer_id),
    ).fetchone():
        return
    raise PermissionError("This customer is outside your active care team.")


def create_care_task(actor_id: str, customer_id: str, title: str, instructions: str, due_date: str,
                     priority: str = "Normal", db_path: Path = DATABASE_PATH) -> str:
    title, instructions = title.strip(), instructions.strip()
    due = date.fromisoformat(due_date)
    if not 3 <= len(title) <= 160 or len(instructions) > 2000:
        raise ValueError("Use a title of 3–160 characters and instructions of at most 2,000 characters.")
    if due < local_today():
        raise ValueError("Choose today or a future due date.")
    if priority not in TASK_PRIORITIES:
        raise ValueError("Choose a valid priority.")
    task_id, now = str(uuid.uuid4()), utc_now()
    with connection(db_path) as conn:
        actor = _active_user(conn, actor_id)
        _authorize_customer(conn, actor, customer_id)
        conn.execute(
            """INSERT INTO care_tasks(id, customer_id, created_by, title, instructions, due_date,
                priority, status, revision, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', 0, ?, ?)""",
            (task_id, customer_id, actor_id, title, instructions, due.isoformat(), priority, now, now),
        )
        conn.execute("INSERT INTO care_task_events VALUES (?, ?, ?, ?, ?, ?)",
                     (str(uuid.uuid4()), task_id, actor_id, "Open", now, 0))
    return task_id


def list_care_tasks(actor_id: str, customer_id: str | None = None, *,
                    db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        actor = _active_user(conn, actor_id)
        clauses, params = [], []
        if customer_id:
            _authorize_customer(conn, actor, customer_id)
            clauses.append("t.customer_id = ?")
            params.append(customer_id)
        elif actor["role"] == "Customer":
            clauses.append("t.customer_id = ?")
            params.append(actor_id)
        elif not actor["is_admin"]:
            clauses.append("EXISTS (SELECT 1 FROM dietitian_customer_links l WHERE l.customer_id = t.customer_id AND l.dietitian_id = ? AND l.status = 'Active')")
            params.append(actor_id)
        sql = "SELECT t.*, u.display_name AS created_by_name FROM care_tasks t JOIN users u ON u.id = t.created_by"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE WHEN t.status IN ('Open', 'In progress') THEN 0 ELSE 1 END, t.due_date, t.created_at"
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def update_care_task(actor_id: str, task_id: str, status: str, *, expected_revision: int,
                     db_path: Path = DATABASE_PATH) -> bool:
    if status not in TASK_STATUSES:
        raise ValueError("Choose a valid task status.")
    with connection(db_path) as conn:
        actor = _active_user(conn, actor_id)
        task = conn.execute("SELECT * FROM care_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise ValueError("Task not found.")
        _authorize_customer(conn, actor, task["customer_id"])
        if actor["role"] == "Customer" and status == "Cancelled" and task["created_by"] != actor_id:
            raise PermissionError("Only your care team can cancel this assigned task.")
        if task["status"] == "Cancelled":
            raise ValueError("Cancelled tasks stay in the history. Create a new task to replace one.")
        now = utc_now()
        changed = conn.execute(
            """UPDATE care_tasks SET status = ?, revision = revision + 1, updated_at = ?, completed_at = ?
               WHERE id = ? AND revision = ?""",
            (status, now, now if status == "Completed" else None, task_id, expected_revision),
        ).rowcount
        if changed:
            conn.execute("INSERT INTO care_task_events VALUES (?, ?, ?, ?, ?, ?)",
                         (str(uuid.uuid4()), task_id, actor_id, status, now, expected_revision + 1))
    return bool(changed)


def list_task_events(actor_id: str, task_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        actor = _active_user(conn, actor_id)
        task = conn.execute("SELECT customer_id FROM care_tasks WHERE id = ?", (task_id,)).fetchone()
        if not task:
            raise ValueError("Task not found.")
        _authorize_customer(conn, actor, task["customer_id"])
        rows = conn.execute(
            """SELECT e.status, e.created_at, u.display_name AS changed_by FROM care_task_events e
               JOIN users u ON u.id = e.actor_id WHERE e.task_id = ? ORDER BY e.revision DESC LIMIT 100""",
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def task_summary(tasks: list[dict[str, Any]], today: date | None = None) -> dict[str, int]:
    day = (today or local_today()).isoformat()
    active = [task for task in tasks if task["status"] in {"Open", "In progress"}]
    return {"open": len(active), "overdue": sum(task["due_date"] < day for task in active),
            "today": sum(task["due_date"] == day for task in active),
            "completed": sum(task["status"] == "Completed" for task in tasks)}


def unread_conversations(user_id: str, db_path: Path = DATABASE_PATH) -> list[dict[str, Any]]:
    with connection(db_path) as conn:
        _active_user(conn, user_id)
        rows = conn.execute(
            """SELECT m.sender_id, u.display_name, COUNT(*) AS unread_count, MAX(m.created_at) AS latest_at
               FROM clinical_messages m JOIN users u ON u.id = m.sender_id
               WHERE m.recipient_id = ? AND m.read_at IS NULL
               GROUP BY m.sender_id, u.display_name ORDER BY latest_at DESC""", (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_conversation_read(user_id: str, sender_id: str, message_ids: list[str],
                            db_path: Path = DATABASE_PATH) -> int:
    ids = list(dict.fromkeys(message_ids))[:500]
    if not ids:
        return 0
    with connection(db_path) as conn:
        _active_user(conn, user_id)
        placeholders = ",".join("?" for _ in ids)
        changed = conn.execute(
            f"UPDATE clinical_messages SET read_at = ? WHERE recipient_id = ? AND sender_id = ? "
            f"AND read_at IS NULL AND id IN ({placeholders})", (utc_now(), user_id, sender_id, *ids),
        ).rowcount
    return changed
