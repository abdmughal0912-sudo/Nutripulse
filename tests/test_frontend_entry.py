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

    def test_authentication_uses_otp_only_for_signup_and_recovery(self) -> None:
        for marker in (
            "np-auth-card-marker", "np-auth-starfield", "Customer sign-up",
            "Dietitian application", "First admin setup", "Private setup code",
            "render_signup_verification", "pending_signup_user", "Forgot password?",
            "render_password_reset", "send_password_reset_code", "send_signup_code",
            "OTP is required only for sign-up and password recovery",
        ):
            self.assertIn(marker, APP_SOURCE)
        self.assertIn("st.tabs(tab_names, default=default_tab)", APP_SOURCE)
        self.assertNotIn("deliver_login_code", APP_SOURCE)
        self.assertNotIn("pending_auth_user", APP_SOURCE)

    def test_theme_has_mobile_and_reduced_motion_rules(self) -> None:
        combined_theme = THEME_SOURCE + LANDING_THEME_SOURCE
        self.assertIn("@media(max-width:720px)", combined_theme)
        self.assertIn("@media(prefers-reduced-motion:reduce)", combined_theme)
        self.assertIn(":has(.np-auth-form-marker)", combined_theme)
        self.assertIn("@keyframes np-marquee", combined_theme)
        self.assertIn('[data-testid="stColumn"]', combined_theme)
        self.assertIn('max-width:100vw', THEME_SOURCE)

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

    def test_latest_verified_lab_report_is_restored_for_planning(self) -> None:
        for marker in (
            "reports = list_lab_reports(active_profile_id)",
            'latest_lab_values = latest_report["values"]',
            "assess_safety(latest_lab_values, saved)",
            "Why this plan is different",
            "How the plan responded",
        ):
            self.assertIn(marker, APP_SOURCE)

    def test_clinical_flags_do_not_render_streamlit_component_objects(self) -> None:
        self.assertNotIn(
            'st.warning(" · ".join(conditions)) if conditions else st.success',
            APP_SOURCE,
        )
        self.assertNotIn(
            'st.error(" · ".join(allergies)) if allergies else st.success',
            APP_SOURCE,
        )
        for marker in (
            'if conditions:',
            'Conditions requiring attention:',
            'if allergies:',
            'Recorded sensitivities:',
        ):
            self.assertIn(marker, APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
