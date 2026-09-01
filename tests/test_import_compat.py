from __future__ import annotations

import importlib
import sys
import unittest

import src.assistant as assistant_module
import src.diet_engine as diet_engine_module
from src.import_compat import load_assistant_exports


class ImportCompatibilityTests(unittest.TestCase):
    def test_current_assistant_exports_load(self) -> None:
        status, capabilities, reply = load_assistant_exports()
        self.assertTrue(callable(status))
        self.assertTrue(callable(capabilities))
        self.assertTrue(callable(reply))

    def test_stale_cached_assistant_is_reloaded(self) -> None:
        original_capabilities = assistant_module.assistant_capabilities
        original_reply = assistant_module.assistant_reply
        try:
            del assistant_module.assistant_capabilities
            del assistant_module.assistant_reply
            status, capabilities, reply = load_assistant_exports()
            self.assertTrue(callable(status))
            self.assertTrue(callable(capabilities))
            self.assertTrue(callable(reply))
        finally:
            if not hasattr(assistant_module, "assistant_capabilities"):
                assistant_module.assistant_capabilities = original_capabilities
            if not hasattr(assistant_module, "assistant_reply"):
                assistant_module.assistant_reply = original_reply
            importlib.reload(assistant_module)

    def test_stale_cached_diet_engine_is_reloaded_before_assistant_retry(self) -> None:
        original_grocery_list = diet_engine_module.grocery_list
        previous_assistant = sys.modules.pop("src.assistant", None)
        try:
            del diet_engine_module.grocery_list
            status, capabilities, reply = load_assistant_exports()
            self.assertTrue(callable(status))
            self.assertTrue(callable(capabilities))
            self.assertTrue(callable(reply))
            self.assertTrue(callable(diet_engine_module.grocery_list))
        finally:
            if not hasattr(diet_engine_module, "grocery_list"):
                diet_engine_module.grocery_list = original_grocery_list
            importlib.reload(diet_engine_module)
            if previous_assistant is not None:
                sys.modules["src.assistant"] = previous_assistant
