from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

from src.account_security import (
    LOGIN_MAX_ATTEMPTS, SESSION_IDLE_SECONDS, SESSION_MAX_SECONDS,
    list_account_events, reserve_login_attempt, revoke_account_sessions, validate_account_session,
)
from src.auth import authenticate_with_status, hash_password
from src.care_tasks import (
    create_care_task, list_care_tasks, list_task_events, mark_conversation_read,
    task_summary, unread_conversations, update_care_task,
)
from src.database import (
    connection, create_user, get_user, get_user_preferences, initialize_database,
    link_dietitian_customer, list_clinical_messages, send_clinical_message,
    update_user_password, update_user_preferences,
)
from src.local_time import local_today


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = hash_password("WorkspaceTest123")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = Path(self.directory.name) / "isolated.db"
        initialize_database(self.db)
        self.customer = self.user("customer", "Customer")
        self.other = self.user("other", "Customer")
        self.dietitian = self.user("dietitian", "Dietitian")
        self.unassigned = self.user("unassigned", "Dietitian")
        self.admin = self.user("admin", "Dietitian", is_admin=True)
        link_dietitian_customer(self.dietitian["id"], self.customer["id"], self.db)

    def user(self, name, role, **kwargs):
        return create_user(name, self.password_hash, role, name.title(), email=f"{name}@example.com",
                           db_path=self.db, approval_status="Approved", **kwargs)

    def task(self, creator=None):
        return create_care_task((creator or self.dietitian)["id"], self.customer["id"],
                                "Review food diary", "Bring recent meal records.", local_today().isoformat(),
                                db_path=self.db)

    def valid_session(self, snapshot, **kwargs):
        return validate_account_session(snapshot, started_at=100, last_active_at=100,
                                        now=kwargs.get("now", 101), db_path=self.db)

    def test_tasks_enforce_customer_and_caseload_boundaries(self):
        self.task()
        self.assertEqual(len(list_care_tasks(self.customer["id"], db_path=self.db)), 1)
        self.assertEqual(list_care_tasks(self.other["id"], db_path=self.db), [])
        self.assertEqual(list_care_tasks(self.unassigned["id"], db_path=self.db), [])
        self.assertEqual(len(list_care_tasks(self.admin["id"], db_path=self.db)), 1)
        for actor in (self.other, self.unassigned):
            with self.subTest(actor=actor["id"]), self.assertRaises(PermissionError):
                list_care_tasks(actor["id"], self.customer["id"], db_path=self.db)
            with self.subTest(actor=actor["id"]), self.assertRaises(PermissionError):
                self.task(actor)

    def test_task_updates_keep_history_and_reject_stale_edits(self):
        task_id = self.task()
        self.assertTrue(update_care_task(self.customer["id"], task_id, "In progress", expected_revision=0, db_path=self.db))
        self.assertFalse(update_care_task(self.dietitian["id"], task_id, "Completed", expected_revision=0, db_path=self.db))
        self.assertTrue(update_care_task(self.customer["id"], task_id, "Completed", expected_revision=1, db_path=self.db))
        events = list_task_events(self.dietitian["id"], task_id, self.db)
        self.assertEqual([item["status"] for item in events], ["Completed", "In progress", "Open"])
        task = list_care_tasks(self.customer["id"], db_path=self.db)[0]
        self.assertIsNotNone(task["completed_at"])
        initialize_database(self.db)
        self.assertEqual(list_task_events(self.customer["id"], task_id, self.db), events)

    def test_customer_cannot_cancel_assigned_task_but_can_cancel_own(self):
        assigned = self.task()
        with self.assertRaises(PermissionError):
            update_care_task(self.customer["id"], assigned, "Cancelled", expected_revision=0, db_path=self.db)
        own = self.task(self.customer)
        self.assertTrue(update_care_task(self.customer["id"], own, "Cancelled", expected_revision=0, db_path=self.db))
        with self.assertRaises(ValueError):
            update_care_task(self.customer["id"], own, "Open", expected_revision=1, db_path=self.db)

    def test_revoked_caseload_blocks_history_and_writes(self):
        task_id = self.task()
        with connection(self.db) as conn:
            conn.execute("UPDATE dietitian_customer_links SET status = 'Inactive'")
        with self.assertRaises(PermissionError):
            update_care_task(self.dietitian["id"], task_id, "Completed", expected_revision=0, db_path=self.db)
        with self.assertRaises(PermissionError):
            list_task_events(self.dietitian["id"], task_id, self.db)
        self.assertEqual(list_care_tasks(self.dietitian["id"], db_path=self.db), [])
        self.assertEqual(len(list_care_tasks(self.customer["id"], db_path=self.db)), 1)

    def test_task_validation_and_local_day_counts(self):
        self.task()
        tasks = list_care_tasks(self.customer["id"], db_path=self.db)
        self.assertEqual(task_summary(tasks)["today"], 1)
        self.assertEqual(task_summary(tasks, local_today() + timedelta(days=1))["overdue"], 1)
        for title, due, priority in [("x", local_today(), "Normal"), ("valid title", local_today()-timedelta(days=1), "Normal"), ("valid title", local_today(), "Urgent")]:
            with self.subTest(title=title, due=due, priority=priority), self.assertRaises(ValueError):
                create_care_task(self.customer["id"], self.customer["id"], title, "", due.isoformat(), priority, self.db)

    def test_inactive_account_cannot_use_care_services(self):
        self.task()
        with connection(self.db) as conn:
            conn.execute("UPDATE users SET active = 0 WHERE id = ?", (self.customer["id"],))
        with self.assertRaises(PermissionError):
            list_care_tasks(self.customer["id"], db_path=self.db)
        with self.assertRaises(PermissionError):
            unread_conversations(self.customer["id"], self.db)
        with self.assertRaises(ValueError):
            send_clinical_message(self.customer["id"], self.dietitian["id"], "Hello", "New message", self.db)

    def test_message_receipts_only_mark_displayed_thread_and_recipient(self):
        cid, did, aid = self.customer["id"], self.dietitian["id"], self.admin["id"]
        first = send_clinical_message(did, cid, "Review", "Please review your diary.", self.db)
        other = send_clinical_message(aid, cid, "Welcome", "Welcome to your care team.", self.db)
        displayed = list_clinical_messages(cid, did, self.db)
        self.assertIsNone(displayed[0]["read_at"])
        self.assertEqual(sum(row["unread_count"] for row in unread_conversations(cid, self.db)), 2)
        later = send_clinical_message(did, cid, "Follow-up", "A new message after the page opened.", self.db)
        self.assertEqual(mark_conversation_read(self.other["id"], did, [first], self.db), 0)
        self.assertEqual(mark_conversation_read(cid, did, [first, other], self.db), 1)
        remaining = {row["id"] for row in list_clinical_messages(cid, db_path=self.db) if not row["read_at"]}
        self.assertEqual(remaining, {later, other})
        self.assertEqual(mark_conversation_read(cid, did, [first], self.db), 0)

    def test_message_limits_and_relationship(self):
        with self.assertRaises(ValueError):
            send_clinical_message(self.unassigned["id"], self.customer["id"], "Subject", "Hello", self.db)
        with self.assertRaises(ValueError):
            send_clinical_message(self.dietitian["id"], self.customer["id"], "Subject", "x" * 4001, self.db)

    def test_login_budget_is_atomic_across_concurrent_sessions(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            accepted = list(pool.map(lambda _: reserve_login_attempt("same-account", self.db, now=1000), range(20)))
        self.assertEqual(sum(accepted), LOGIN_MAX_ATTEMPTS)
        self.assertFalse(reserve_login_attempt("same-account", self.db, now=1899))
        self.assertTrue(reserve_login_attempt("same-account", self.db, now=1900))

    def test_email_username_share_limit_and_recovery_clears_it(self):
        for index in range(LOGIN_MAX_ATTEMPTS):
            identifier = "CUSTOMER@example.com" if index % 2 else "Customer"
            user, error = authenticate_with_status(identifier, "wrong", db_path=self.db)
            self.assertIsNone(user)
            self.assertIn("Incorrect", error)
        user, error = authenticate_with_status("customer@example.com", "WorkspaceTest123", db_path=self.db)
        self.assertIsNone(user)
        self.assertIn("Too many", error)
        self.assertTrue(update_user_password(self.customer["id"], self.password_hash, self.db))
        user, error = authenticate_with_status("customer@example.com", "WorkspaceTest123", db_path=self.db)
        self.assertEqual(error, "Signed in.")
        self.assertNotIn("password_hash", user)

    def test_success_clears_failures_and_records_safe_activity(self):
        authenticate_with_status("customer", "wrong", db_path=self.db)
        authenticate_with_status("customer", "WorkspaceTest123", db_path=self.db)
        with connection(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS count FROM login_attempts").fetchone()["count"], 0)
        events = list_account_events(self.customer["id"], self.db)
        self.assertEqual({row["action"] for row in events}, {"Signed in", "Incorrect password"})
        self.assertEqual(set(events[0]), {"action", "created_at"})
        self.assertEqual(list_account_events(self.other["id"], self.db), [])

    def test_session_revocation_preserves_records_and_preferences(self):
        self.task()
        update_user_preferences(self.customer["id"], voice_alerts=True, voice_replies=True, message_sounds=True, db_path=self.db)
        self.assertIsNotNone(self.valid_session(self.customer))
        revoke_account_sessions(self.customer["id"], self.db)
        self.assertIsNone(self.valid_session(self.customer))
        fresh = get_user(self.customer["id"], self.db)
        self.assertIsNotNone(self.valid_session(fresh))
        self.assertEqual(len(list_care_tasks(self.customer["id"], db_path=self.db)), 1)
        self.assertTrue(all(get_user_preferences(self.customer["id"], self.db).values()))

    def test_password_change_invalidates_existing_sessions(self):
        self.assertTrue(update_user_password(self.customer["id"], self.password_hash, self.db))
        self.assertIsNone(self.valid_session(self.customer))

    def test_backup_import_preserves_new_records_without_overwriting(self):
        from scripts.migrate_sqlite_to_postgres import migrate
        self.task()
        update_user_preferences(self.customer["id"], voice_alerts=True, voice_replies=True,
                                message_sounds=True, db_path=self.db)
        revoke_account_sessions(self.customer["id"], self.db)
        target = Path(self.directory.name) / "migration-target.db"
        with patch("scripts.migrate_sqlite_to_postgres.database_backend", return_value={"engine": "PostgreSQL"}), \
             patch("scripts.migrate_sqlite_to_postgres.initialize_database", side_effect=lambda: initialize_database(target)), \
             patch("scripts.migrate_sqlite_to_postgres.connection", side_effect=lambda: connection(target)):
            counts = migrate(self.db)
            second = migrate(self.db)
        self.assertEqual(counts["care_tasks"], 1)
        self.assertEqual(counts["care_task_events"], 1)
        self.assertEqual(counts["user_preferences"], 1)
        self.assertEqual(counts["account_events"], 1)
        self.assertEqual(sum(second.values()), 0)
        self.assertTrue(all(get_user_preferences(self.customer["id"], target).values()))
        self.assertEqual(len(list_care_tasks(self.customer["id"], db_path=target)), 1)

    def test_session_timeout_and_changed_access(self):
        self.assertIsNone(self.valid_session(self.customer, now=100 + SESSION_IDLE_SECONDS))
        self.assertIsNone(validate_account_session(self.customer, started_at=100,
                          last_active_at=100 + SESSION_MAX_SECONDS - 1, now=100 + SESSION_MAX_SECONDS, db_path=self.db))
        for field, value in [("active", 0), ("approval_status", "Rejected"), ("is_admin", 1), ("email_verified_at", None)]:
            with self.subTest(field=field), connection(self.db) as conn:
                conn.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (value, self.customer["id"]))
            self.assertIsNone(self.valid_session(self.customer))
            with connection(self.db) as conn:
                conn.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (self.customer[field], self.customer["id"]))


if __name__ == "__main__":
    unittest.main()
