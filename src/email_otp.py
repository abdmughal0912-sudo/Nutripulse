"""Email-delivered one-time codes for sign-up verification and password recovery."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any


OTP_EXPIRY_SECONDS = 10 * 60
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
EMAIL_PATTERN = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$", re.I)


class EmailDeliveryError(RuntimeError):
    """Raised when a verification message cannot be delivered."""


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    sender_email: str
    sender_name: str = "NutriPulse AI"

    def validate(self) -> None:
        if not self.host.strip():
            raise ValueError("NUTRIPULSE_SMTP_HOST is not configured.")
        if not 1 <= int(self.port) <= 65535:
            raise ValueError("NUTRIPULSE_SMTP_PORT must be a valid port number.")
        if not self.username.strip() or not self.password.strip():
            raise ValueError("NUTRIPULSE_SMTP_USERNAME and NUTRIPULSE_SMTP_PASSWORD are required.")
        if not is_valid_email_address(self.sender_email):
            raise ValueError("NUTRIPULSE_SMTP_SENDER_EMAIL must be a valid email address.")


def is_valid_email_address(value: str) -> bool:
    email = str(value or "").strip()
    return bool(email and len(email) <= 254 and EMAIL_PATTERN.fullmatch(email))


def mask_email(value: str) -> str:
    email = str(value or "").strip()
    if not is_valid_email_address(email):
        return "your registered email"
    local, domain = email.split("@", 1)
    shown = local[:2] if len(local) > 2 else local[:1]
    return f"{shown}{'*' * max(2, len(local) - len(shown))}@{domain}"


def create_login_challenge(user_id: str, email: str, now: float | None = None) -> tuple[dict[str, Any], str]:
    if not is_valid_email_address(email):
        raise ValueError("A valid email address is required for verification.")
    issued_at = float(time.time() if now is None else now)
    code = f"{secrets.randbelow(1_000_000):06d}"
    nonce = secrets.token_hex(16)
    digest = hashlib.sha256(f"{nonce}:{code}".encode("utf-8")).hexdigest()
    challenge: dict[str, Any] = {
        "user_id": str(user_id),
        "email": email.strip().lower(),
        "nonce": nonce,
        "digest": digest,
        "issued_at": issued_at,
        "expires_at": issued_at + OTP_EXPIRY_SECONDS,
        "attempts": 0,
    }
    return challenge, code


def verify_login_code(
    challenge: dict[str, Any], user_id: str, submitted_code: str, now: float | None = None,
) -> tuple[bool, str]:
    current_time = float(time.time() if now is None else now)
    if str(challenge.get("user_id", "")) != str(user_id):
        return False, "This verification request does not match the account."
    if current_time > float(challenge.get("expires_at", 0)):
        return False, "The verification code has expired. Request a new code."
    attempts = int(challenge.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        return False, "Too many incorrect attempts. Request a new code."
    code = str(submitted_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        challenge["attempts"] = attempts + 1
        return False, "Enter the complete six-digit verification code."
    actual = hashlib.sha256(f"{challenge.get('nonce', '')}:{code}".encode("utf-8")).hexdigest()
    if not hmac.compare_digest(actual, str(challenge.get("digest", ""))):
        challenge["attempts"] = attempts + 1
        remaining = max(0, OTP_MAX_ATTEMPTS - int(challenge["attempts"]))
        return False, f"Incorrect verification code. {remaining} attempt(s) remaining."
    return True, "Email verified."


def resend_wait_seconds(challenge: dict[str, Any] | None, now: float | None = None) -> int:
    if not challenge:
        return 0
    current_time = float(time.time() if now is None else now)
    elapsed = current_time - float(challenge.get("issued_at", 0))
    return max(0, int(OTP_RESEND_SECONDS - elapsed + 0.999))


def _send_security_code(
    settings: SmtpSettings, recipient_email: str, recipient_name: str, code: str,
    *, purpose: str,
) -> None:
    settings.validate()
    if not is_valid_email_address(recipient_email):
        raise ValueError("A valid recipient email address is required.")
    if not re.fullmatch(r"\d{6}", str(code)):
        raise ValueError("Verification codes must contain six digits.")

    message = EmailMessage()
    is_reset = purpose == "password-reset"
    message["Subject"] = (
        f"{code} is your NutriPulse password reset code"
        if is_reset else f"{code} is your NutriPulse sign-up verification code"
    )
    message["From"] = formataddr((settings.sender_name, settings.sender_email))
    message["To"] = recipient_email
    safe_name = str(recipient_name or "NutriPulse user").strip()
    message.set_content(
        f"Hello {safe_name},\n\n"
        f"Your NutriPulse {'password reset' if is_reset else 'account sign-up verification'} code is: {code}\n\n"
        "This code expires in 10 minutes and can be used only once. "
        f"If you did not try to {'reset your password' if is_reset else 'create this account'}, "
        "do not share this code and you can ignore this email.\n\n"
        "NutriPulse AI Security"
    )

    try:
        if int(settings.port) == 465:
            with smtplib.SMTP_SSL(
                settings.host, int(settings.port), timeout=20, context=ssl.create_default_context(),
            ) as smtp:
                smtp.login(settings.username, settings.password)
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings.host, int(settings.port), timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(settings.username, settings.password)
                smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError(
            "The verification email could not be sent. Try again or contact the Administrator."
        ) from exc


def send_signup_code(
    settings: SmtpSettings, recipient_email: str, recipient_name: str, code: str,
) -> None:
    _send_security_code(
        settings, recipient_email, recipient_name, code, purpose="sign-up",
    )


def send_login_code(
    settings: SmtpSettings, recipient_email: str, recipient_name: str, code: str,
) -> None:
    """Backward-compatible alias; interactive logins no longer send an OTP."""
    send_signup_code(settings, recipient_email, recipient_name, code)


def send_password_reset_code(
    settings: SmtpSettings, recipient_email: str, recipient_name: str, code: str,
) -> None:
    _send_security_code(
        settings, recipient_email, recipient_name, code, purpose="password-reset",
    )
