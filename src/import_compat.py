"""Compatibility imports for hosts that retain modules across app hot reloads."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any


ASSISTANT_EXPORTS = (
    "assistant_api_status",
    "assistant_capabilities",
    "assistant_reply",
)


def _missing_exports(module: ModuleType) -> list[str]:
    return [name for name in ASSISTANT_EXPORTS if not callable(getattr(module, name, None))]


def _reload_if_loaded(module_name: str) -> None:
    module = sys.modules.get(module_name)
    if module is not None:
        importlib.reload(module)


def load_assistant_exports() -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    """Load current NutriGuide exports, recovering from Streamlit's stale module cache."""
    importlib.invalidate_caches()
    try:
        module = importlib.import_module("src.assistant")
    except ImportError:
        # A current assistant can fail while importing from an older cached diet engine.
        _reload_if_loaded("src.diet_engine")
        sys.modules.pop("src.assistant", None)
        module = importlib.import_module("src.assistant")

    if _missing_exports(module):
        _reload_if_loaded("src.diet_engine")
        module = importlib.reload(module)

    missing = _missing_exports(module)
    if missing:
        names = ", ".join(missing)
        raise ImportError(f"NutriGuide module is missing required exports after reload: {names}")

    return tuple(getattr(module, name) for name in ASSISTANT_EXPORTS)  # type: ignore[return-value]
