"""Local account authentication with standard-library PBKDF2 password hashing."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Any

from .database import create_user, get_user_by_username, has_admin, record_login


ITERATIONS = 310_000


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_text)
        expected = base64.b64decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def register_account(username: str, password: str, role: str, display_name: str,
                     email: str = "", credential: str = "") -> dict[str, Any]:
    clean_username = username.strip()
    if not (3 <= len(clean_username) <= 40) or not clean_username.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Username must be 3–40 letters, numbers, hyphens, or underscores.")
    if role not in {"Customer", "Dietitian"}:
        raise ValueError("Choose Customer or Dietitian.")
    if len(display_name.strip()) < 2:
        raise ValueError("Enter your full display name.")
    if get_user_by_username(clean_username):
        raise ValueError("That username is already registered.")
    return create_user(clean_username, hash_password(password), role, display_name, email, credential)


def register_admin_account(username: str, password: str, display_name: str,
                           email: str = "") -> dict[str, Any]:
    if has_admin():
        raise ValueError("The first administrator has already been configured.")
    clean_username = username.strip()
    if not (3 <= len(clean_username) <= 40) or not clean_username.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Username must be 3–40 letters, numbers, hyphens, or underscores.")
    if len(display_name.strip()) < 2:
        raise ValueError("Enter the administrator's full name.")
    if get_user_by_username(clean_username):
        raise ValueError("That username is already registered.")
    return create_user(
        clean_username, hash_password(password), "Dietitian", display_name, email,
        "System Administrator", approval_status="Approved", is_admin=True,
    )


def authenticate_with_status(
    username: str, password: str, *, record_success: bool = True,
) -> tuple[dict[str, Any] | None, str]:
    user = get_user_by_username(username)
    if not user or not verify_password(password, str(user["password_hash"])):
        return None, "Incorrect username or password."
    approval = str(user.get("approval_status", "Approved"))
    if str(user.get("role")) == "Dietitian" and approval == "Pending":
        return None, "Your Dietitian application is awaiting administrator approval."
    if approval == "Rejected":
        return None, "This Dietitian application was not approved. Contact the administrator."
    if not int(user.get("active", 0)):
        return None, "This account is inactive. Contact the administrator."
    if record_success:
        record_login(str(user["id"]))
    return {key: value for key, value in user.items() if key != "password_hash"}, "Signed in."


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    return authenticate_with_status(username, password)[0]
