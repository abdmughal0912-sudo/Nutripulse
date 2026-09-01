from __future__ import annotations

import unittest
from pathlib import Path

from src.constants import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_complete_project_document_tracks_implemented_release(self) -> None:
        document = (ROOT / "docs" / "NUTRIPULSE_COMPLETE_PROJECT_DOCUMENT.md").read_text(
            encoding="utf-8"
        )
        required_markers = [
            f"**Application version:** {APP_VERSION}",
            "NUTRIPULSE_DATABASE_URL",
            "OTP is not requested on every login",
            "DIETITIAN IS LIVE",
            "DIETITIAN IS OFFLINE",
            "NUTRIPULSE_PRESENCE_TTL_SECONDS",
            "Voice replies",
            "Message sounds",
            "Voice alerts",
            "Why this plan is different",
            "Food Vision",
            "47,152 classifier-ready unique food profiles",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, document)

    def test_primary_documents_link_to_complete_document(self) -> None:
        target = "docs/NUTRIPULSE_COMPLETE_PROJECT_DOCUMENT.md"
        self.assertIn(target, (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(target, (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8"))

    def test_release_history_includes_email_and_mobile_releases(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## 4.4.0", changelog)
        self.assertIn("## 4.4.1", changelog)


if __name__ == "__main__":
    unittest.main()
