"""Fast startup diagnostic used by the Windows launchers."""

from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_MODULES = [
    "streamlit", "fastapi", "uvicorn", "pandas", "numpy", "plotly",
    "PIL", "cv2", "rapidocr", "pypdfium2", "requests", "pdfplumber", "reportlab",
]
OPTIONAL_MODULES = ["onnxruntime"]


def main() -> int:
    print(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    if not ((3, 11) <= sys.version_info[:2] <= (3, 12)):
        print("ERROR: NutriPulse requires Python 3.11 or 3.12.")
        return 2
    failures: list[str] = []
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
            print(f"OK: {name}")
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    if failures:
        print("\nRUNTIME CHECK FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    for name in OPTIONAL_MODULES:
        try:
            importlib.import_module(name)
            print(f"OK: {name}")
        except Exception as exc:
            print(f"OPTIONAL WARNING: {name}: {type(exc).__name__}: {exc}")
            print("Food Vision will use OpenCV DNN. Bundled OCR will try its configured fallback.")
    try:
        import api
        from src.ml_engine import food_vision_status, model_status

        classifier = model_status()
        vision = food_vision_status()
        print(f"Nutrition classifier: {classifier.get('status')}")
        print(f"Food Vision: {vision.get('status')}")
        print(f"API: {api.app.title}")
    except Exception as exc:
        print(f"APPLICATION IMPORT FAILED: {type(exc).__name__}: {exc}")
        return 1
    print("NUTRIPULSE_RUNTIME_CHECK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
