from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.database import _PostgresConnection, _postgres_sql, database_backend, initialize_database


class FakeRawConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, statement: str, parameters: tuple[object, ...]) -> object:
        self.calls.append((statement, parameters))
        return object()


class DatabaseBackendTests(unittest.TestCase):
    def test_postgres_placeholder_translation(self) -> None:
        self.assertEqual(
            _postgres_sql("SELECT * FROM users WHERE id = ? AND active = ?"),
            "SELECT * FROM users WHERE id = %s AND active = %s",
        )
        raw = FakeRawConnection()
        adapter = _PostgresConnection(raw)
        adapter.execute("SELECT * FROM users WHERE id = ?", ("user-1",))
        self.assertEqual(
            raw.calls,
            [("SELECT * FROM users WHERE id = %s", ("user-1",))],
        )

    def test_cloud_url_selects_postgres_only_for_live_database(self) -> None:
        with patch.dict(
            "os.environ",
            {"NUTRIPULSE_DATABASE_URL": "postgresql://example.invalid/app"},
        ):
            self.assertEqual(database_backend()["engine"], "PostgreSQL")
            with tempfile.TemporaryDirectory() as directory:
                explicit_path = Path(directory) / "isolated.db"
                self.assertEqual(database_backend(explicit_path)["engine"], "SQLite")
                initialize_database(explicit_path)
                self.assertTrue(explicit_path.is_file())

    def test_no_cloud_url_keeps_local_sqlite(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            backend = database_backend()
        self.assertEqual(backend["engine"], "SQLite")
        self.assertFalse(backend["cloud_persistent"])


if __name__ == "__main__":
    unittest.main()
