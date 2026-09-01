"""One-time source refresh for hosts that reuse Python across code deployments."""

from __future__ import annotations

import hashlib
import importlib
import sys
from collections.abc import Iterable
from pathlib import Path


_ACTIVE_SOURCE_FINGERPRINT: str | None = None


def source_fingerprint(project_root: Path | None = None) -> str:
    """Hash application Python sources so a deployed code change is detectable."""
    root = project_root or Path(__file__).resolve().parents[1]
    candidates = [root / "app.py", root / "api.py"]
    candidates.extend(sorted((root / "src").glob("*.py")))
    digest = hashlib.sha256()
    for path in candidates:
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _purge_project_modules(module_names: Iterable[str] | None = None) -> int:
    """Remove loaded NutriPulse submodules, retaining this bootstrap module."""
    names = tuple(module_names) if module_names is not None else tuple(sys.modules)
    removed = 0
    for name in sorted(names, reverse=True):
        if name.startswith("src.") and name != __name__ and name in sys.modules:
            sys.modules.pop(name, None)
            removed += 1
    return removed


def refresh_project_modules() -> bool:
    """Refresh stale project modules once after Python source files change."""
    global _ACTIVE_SOURCE_FINGERPRINT
    importlib.invalidate_caches()
    fingerprint = source_fingerprint()
    if fingerprint == _ACTIVE_SOURCE_FINGERPRINT:
        return False
    _purge_project_modules()
    _ACTIVE_SOURCE_FINGERPRINT = fingerprint
    return True
