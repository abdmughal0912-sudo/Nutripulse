from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_SOURCE = (ROOT / "app.py").read_text(encoding="utf-8")
THEME_SOURCE = (ROOT / "src" / "theme.py").read_text(encoding="utf-8")
LANDING_THEME_SOURCE = (ROOT / "src" / "landing_theme.py").read_text(encoding="utf-8")
PORTAL_THEME_SOURCE = (ROOT / "src" / "portal_theme.py").read_text(encoding="utf-8")


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
            "np-auth-card-marker", "np-auth-starfield", "Customer sign-up",
            "Dietitian application", "First admin setup", "Private setup code",
            "render_email_verification", "pending_auth_user", "Forgot password?",
            "render_password_reset", "send_password_reset_code",
        ):
            self.assertIn(marker, APP_SOURCE)
        self.assertIn("st.tabs(tab_names, default=default_tab)", APP_SOURCE)

    def test_theme_has_mobile_and_reduced_motion_rules(self) -> None:
        combined_theme = THEME_SOURCE + LANDING_THEME_SOURCE
        self.assertIn("@media(max-width:720px)", combined_theme)
        self.assertIn("@media(prefers-reduced-motion:reduce)", combined_theme)
        self.assertIn(":has(.np-auth-form-marker)", combined_theme)
        self.assertIn("@keyframes np-marquee", combined_theme)

    def test_cloud_theme_clears_toolbar_and_animates_coloured_wave(self) -> None:
        self.assertIn('padding-top:4.9rem!important', LANDING_THEME_SOURCE)
        self.assertIn('[data-testid="stMainBlockContainer"]', LANDING_THEME_SOURCE)
        self.assertIn('.np-marquee-track span:nth-child(6n+1)', LANDING_THEME_SOURCE)
        self.assertIn('@keyframes np-word-wave', LANDING_THEME_SOURCE)

    def test_portals_have_readable_type_pastels_and_star_wave(self) -> None:
        self.assertIn('np-portal-marker', APP_SOURCE)
        self.assertIn('font-size:.96rem!important', PORTAL_THEME_SOURCE)
        self.assertIn('@keyframes np-portal-stars', PORTAL_THEME_SOURCE)
        self.assertIn('rgba(165,243,252,.16)', PORTAL_THEME_SOURCE)

    def test_authentication_is_a_compact_centered_board(self) -> None:
        self.assertIn('max-width:720px!important', PORTAL_THEME_SOURCE)
        self.assertIn(':has(.np-auth-card-marker)', PORTAL_THEME_SOURCE)
        self.assertIn('[data-testid="stColumn"]', PORTAL_THEME_SOURCE)


if __name__ == "__main__":
    unittest.main()
