from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

from src.runtime_refresh import _purge_project_modules, source_fingerprint


class RuntimeRefreshTests(unittest.TestCase):
    def test_source_fingerprint_changes_with_python_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "app.py").write_text("APP = 1\n", encoding="utf-8")
            (root / "api.py").write_text("API = 1\n", encoding="utf-8")
            (root / "src" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
            first = source_fingerprint(root)
            (root / "src" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
            self.assertNotEqual(first, source_fingerprint(root))

    def test_purge_removes_only_selected_project_modules(self) -> None:
        stale_name = "src._nutripulse_stale_runtime_probe"
        external_name = "nutripulse_external_runtime_probe"
        sys.modules[stale_name] = ModuleType(stale_name)
        sys.modules[external_name] = ModuleType(external_name)
        try:
            removed = _purge_project_modules([stale_name, external_name])
            self.assertEqual(removed, 1)
            self.assertNotIn(stale_name, sys.modules)
            self.assertIn(external_name, sys.modules)
        finally:
            sys.modules.pop(stale_name, None)
            sys.modules.pop(external_name, None)
