from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
THEME_SOURCE = (ROOT / "src" / "theme.py").read_text(encoding="utf-8")


class FrontendEntryTests(unittest.TestCase):
    def test_public_landing_has_required_actions_and_sections(self) -> None:
        for marker in (
            "np-landing-nav-marker", "np-landing-copy", "np-marquee-track",
            "np-feature-grid", "np-landing-proof", "landing_login_top",
            "landing_signup_top", "landing_signup_hero", "landing_login_hero",
        ):
            self.assertIn(marker, APP_SOURCE)

    def test_authentication_preserves_all_role_flows_and_email_otp(self) -> None:
        for marker in (
            "np-auth-form-marker", "np-auth-visual", "Customer sign-up",
            "Dietitian application", "First admin setup", "Private setup code",
            "render_email_verification", "pending_auth_user",
        ):
            self.assertIn(marker, APP_SOURCE)
        self.assertIn("st.tabs(tab_names, default=default_tab)", APP_SOURCE)

    def test_theme_has_mobile_and_reduced_motion_rules(self) -> None:
        self.assertIn("@media(max-width:720px)", THEME_SOURCE)
        self.assertIn("@media(prefers-reduced-motion:reduce)", THEME_SOURCE)
        self.assertIn(":has(.np-auth-form-marker)", THEME_SOURCE)
        self.assertIn("@keyframes np-marquee", THEME_SOURCE)


if __name__ == "__main__":
    unittest.main()
