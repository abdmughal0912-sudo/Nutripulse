from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src.auth import authenticate_with_status, hash_password, verify_password
from src.database import (
    create_user, get_user, initialize_database, reserve_email_otp_delivery,
    set_verified_user_email, update_user_password,
)
from src.email_otp import (
    OTP_MAX_ATTEMPTS,
    SmtpSettings,
    create_login_challenge,
    is_valid_email_address,
    mask_email,
    resend_wait_seconds,
    send_password_reset_code,
    send_signup_code,
    verify_login_code,
)


class EmailOtpTests(unittest.TestCase):
    def test_email_validation_and_masking(self) -> None:
        self.assertTrue(is_valid_email_address("person@example.com"))
        self.assertFalse(is_valid_email_address("not-an-email"))
        self.assertEqual(mask_email("person@example.com"), "pe****@example.com")

    def test_challenge_accepts_correct_code_and_expires(self) -> None:
        challenge, code = create_login_challenge("user-1", "person@example.com", now=100.0)
        verified, _ = verify_login_code(challenge, "user-1", code, now=101.0)
        self.assertTrue(verified)
        expired, message = verify_login_code(challenge, "user-1", code, now=701.0)
        self.assertFalse(expired)
        self.assertIn("expired", message.lower())

    def test_challenge_limits_incorrect_attempts(self) -> None:
        challenge, code = create_login_challenge("user-1", "person@example.com", now=100.0)
        wrong = "000000" if code != "000000" else "999999"
        for _ in range(OTP_MAX_ATTEMPTS):
            verified, _ = verify_login_code(challenge, "user-1", wrong, now=101.0)
            self.assertFalse(verified)
        verified, message = verify_login_code(challenge, "user-1", code, now=102.0)
        self.assertFalse(verified)
        self.assertIn("too many", message.lower())

    def test_resend_cooldown(self) -> None:
        challenge, _ = create_login_challenge("user-1", "person@example.com", now=100.0)
        self.assertEqual(resend_wait_seconds(challenge, now=100.0), 60)
        self.assertEqual(resend_wait_seconds(challenge, now=160.0), 0)

    @patch("src.email_otp.smtplib.SMTP")
    def test_signup_smtp_uses_tls_and_authentication(self, smtp_class) -> None:
        smtp = smtp_class.return_value.__enter__.return_value
        settings = SmtpSettings(
            host="smtp.gmail.com", port=587, username="sender@gmail.com",
            password="app-password", sender_email="sender@gmail.com",
        )
        send_signup_code(settings, "person@example.com", "Person", "123456")
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("sender@gmail.com", "app-password")
        smtp.send_message.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        self.assertIn("sign-up", str(message["Subject"]).lower())

    @patch("src.email_otp.smtplib.SMTP")
    def test_password_reset_email_is_clearly_identified(self, smtp_class) -> None:
        smtp = smtp_class.return_value.__enter__.return_value
        settings = SmtpSettings(
            host="smtp.gmail.com", port=587, username="sender@gmail.com",
            password="app-password", sender_email="sender@gmail.com",
        )
        send_password_reset_code(settings, "person@example.com", "Person", "654321")
        message = smtp.send_message.call_args.args[0]
        self.assertIn("password reset", str(message["Subject"]).lower())
        self.assertIn("password reset", message.get_content().lower())

    def test_verified_email_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "otp.db"
            initialize_database(db_path)
            user = create_user(
                "otp_user", hash_password("SecurePass123"), "Customer", "OTP User",
                email="verified@example.com", db_path=db_path, email_verified=False,
            )
            self.assertFalse(user["email_verified_at"])
            self.assertEqual(user["active"], 0)
            self.assertTrue(set_verified_user_email(user["id"], "Verified@Example.com", db_path))
            saved = get_user(user["id"], db_path)
            self.assertEqual(saved["email"], "verified@example.com")
            self.assertTrue(saved["email_verified_at"])
            self.assertEqual(saved["active"], 1)

    def test_verified_reset_replaces_pbkdf2_password(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "password-reset.db"
            initialize_database(db_path)
            user = create_user(
                "reset_user", hash_password("OriginalPass123"), "Customer", "Reset User",
                email="reset@example.com", db_path=db_path,
            )
            replacement = hash_password("ReplacementPass123")
            self.assertTrue(update_user_password(user["id"], replacement, db_path))
            saved = get_user(user["id"], db_path)
            self.assertFalse(verify_password("OriginalPass123", saved["password_hash"]))
            self.assertTrue(verify_password("ReplacementPass123", saved["password_hash"]))

    def test_database_delivery_rate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / "rate-limit.db"
            initialize_database(db_path)
            user = create_user(
                "rate_user", hash_password("SecurePass123"), "Customer", "Rate User",
                db_path=db_path,
            )
            start = datetime(2026, 8, 29, 10, 0, tzinfo=timezone.utc)
            allowed, wait = reserve_email_otp_delivery(user["id"], db_path, now=start)
            self.assertTrue(allowed)
            self.assertEqual(wait, 0)
            allowed, wait = reserve_email_otp_delivery(
                user["id"], db_path, now=start + timedelta(seconds=1),
            )
            self.assertFalse(allowed)
            self.assertEqual(wait, 59)

    def test_password_validation_can_defer_login_recording(self) -> None:
        encoded = hash_password("SecurePass123")
        fake_user = {
            "id": "user-1", "username": "person", "password_hash": encoded,
            "role": "Customer", "display_name": "Person", "email": "person@example.com",
            "active": 1, "approval_status": "Approved", "is_admin": 0,
            "email_verified_at": "2026-08-31T12:00:00+00:00",
        }
        with patch("src.auth.get_user_by_username", return_value=fake_user), patch(
            "src.auth.record_login",
        ) as record_login:
            user, message = authenticate_with_status(
                "person", "SecurePass123", record_success=False,
            )
        self.assertIsNotNone(user)
        self.assertEqual(message, "Signed in.")
        record_login.assert_not_called()

    def test_unverified_signup_requires_otp_but_verified_login_does_not(self) -> None:
        encoded = hash_password("SecurePass123")
        pending = {
            "id": "user-2", "username": "new_person", "password_hash": encoded,
            "role": "Customer", "display_name": "New Person", "email": "new@example.com",
            "active": 1, "approval_status": "Approved", "is_admin": 0,
            "email_verified_at": None,
        }
        with patch("src.auth.get_user_by_username", return_value=pending), patch(
            "src.auth.record_login",
        ) as record_login:
            user, message = authenticate_with_status("new_person", "SecurePass123")
        self.assertIsNotNone(user)
        self.assertIn("verification required", message.lower())
        record_login.assert_not_called()

        verified = dict(pending, email_verified_at="2026-08-31T12:00:00+00:00")
        with patch("src.auth.get_user_by_username", return_value=verified), patch(
            "src.auth.record_login",
        ) as record_login:
            user, message = authenticate_with_status("new_person", "SecurePass123")
        self.assertIsNotNone(user)
        self.assertEqual(message, "Signed in.")
        record_login.assert_called_once_with("user-2")


if __name__ == "__main__":
    unittest.main()
