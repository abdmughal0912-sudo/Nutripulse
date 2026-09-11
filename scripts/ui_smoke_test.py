from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DB_PATH = Path(tempfile.gettempdir()) / "nutripulse_v4_ui_smoke.db"
if DB_PATH.exists():
    DB_PATH.unlink()
os.environ["NUTRIPULSE_DATABASE_PATH"] = str(DB_PATH)

from src.auth import hash_password
from src.database import (
    create_meal_schedule, create_user, initialize_database, link_dietitian_customer,
    save_plan, upsert_profile, get_user_preferences, send_clinical_message,
)
from src.diet_engine import generate_plan
from src.care_tasks import create_care_task, list_care_tasks, unread_conversations
from src.account_security import revoke_account_sessions
from src.local_time import local_today

PAGES = [
    "◈  Overview",
    "◉  Alert Center",
    "◎  My Profile",
    "⌁  Laboratory Intelligence",
    "▦  Smart Diet Planner",
    "◉  Food Vision & Diary",
    "⌕  Food Library",
    "↗  Progress Analytics",
    "✦  Care Team",
    "✓  Care Tasks",
    "✉  Care Inbox",
    "⚙  Account & Security",
    "✧  NutriGuide Assistant",
    "◆  Nutrition Classifier",
    "⌘  Evidence Web & API",
]

DIETITIAN_PAGES = [
    "✦  Clinical Dashboard",
    "◈  Customer Overview",
    "◉  Food Diary Review",
    "▦  Diet Plan Oversight",
    "⌁  Reports & Lab Analysis",
    "↗  Progress Analytics",
    "◆  Notes & Prescriptions",
    "✉  Questions & Messaging",
    "✓  Care Tasks",
    "✉  Care Inbox",
    "⚙  Account & Security",
]

ADMIN_PAGES = [
    *DIETITIAN_PAGES,
    "⚙  Administrator Governance",
    "⌘  Dataset & Model Audit",
]


def main() -> None:
    initialize_database(DB_PATH)
    landing_app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    landing_app.run()
    landing_errors = [str(exception.value) for exception in landing_app.exception]
    if landing_errors:
        raise AssertionError(f"Public landing: {landing_errors}")
    print("PUBLIC LANDING: PASS")
    auth_app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    auth_app.session_state["entry_view"] = "auth"
    auth_app.run()
    auth_errors = [str(exception.value) for exception in auth_app.exception]
    if auth_errors:
        raise AssertionError(f"Authentication: {auth_errors}")
    print("AUTHENTICATION: PASS")
    user = create_user("smoke_customer", hash_password("SmokePass123"), "Customer", "Smoke Customer", db_path=DB_PATH)
    dietitian = create_user(
        "smoke_dietitian", hash_password("DietitianPass123"), "Dietitian", "Smoke Dietitian",
        credential="RD-SMOKE", db_path=DB_PATH, approval_status="Approved",
    )
    admin = create_user(
        "smoke_admin", hash_password("AdministratorPass123"), "Dietitian", "Smoke Administrator",
        credential="System Administrator", db_path=DB_PATH, approval_status="Approved", is_admin=True,
    )
    customer_profile = {
        "id": user["id"], "name": user["display_name"], "age": 30,
        "biological_sex": "Male", "height_cm": 175.0, "weight_kg": 75.0,
        "activity": "Moderately active", "goal": "Maintenance",
        "cuisine": "Pakistani + international", "conditions": [], "allergies": [], "medications": "",
    }
    upsert_profile(customer_profile, DB_PATH)
    upsert_profile({
        "id": dietitian["id"], "name": dietitian["display_name"], "age": 35,
        "biological_sex": "Female", "height_cm": 165.0, "weight_kg": 65.0,
        "activity": "Moderately active", "goal": "Maintenance",
        "cuisine": "Mediterranean", "conditions": [], "allergies": [], "medications": "",
    }, DB_PATH)
    link_dietitian_customer(dietitian["id"], user["id"], DB_PATH)
    create_care_task(dietitian["id"], user["id"], "Bring your food diary",
                    "Include recent meals.", local_today().isoformat(), db_path=DB_PATH)
    send_clinical_message(dietitian["id"], user["id"], "Diary review",
                          "Please bring your diary to the review.", DB_PATH)
    plan = generate_plan(customer_profile, [])
    plan_id = save_plan(user["id"], plan, db_path=DB_PATH)
    create_meal_schedule(user["id"], plan_id, plan, "2026-08-24", DB_PATH)
    safe_user = {key: value for key, value in user.items() if key != "password_hash"}
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    app.session_state["current_user"] = safe_user
    app.run()
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        errors = [str(exception.value) for exception in app.exception]
        if errors:
            raise AssertionError(f"{page}: {errors}")
        print(f"{page}: PASS")
    # Exercise stateful controls, including hidden widget cleanup between pages.
    app.sidebar.radio[0].set_value("⚙  Account & Security").run()
    app.toggle(key="assistant_voice_enabled").set_value(True).run()
    app.toggle(key="assistant_sound_enabled").set_value(True).run()
    app.sidebar.radio[0].set_value("◈  Overview").run()
    app.toggle(key="voice_alerts_enabled").set_value(True).run()
    app.sidebar.radio[0].set_value("⚙  Account & Security").run()
    assert app.toggle(key="assistant_voice_enabled").value
    assert app.toggle(key="assistant_sound_enabled").value
    assert all(get_user_preferences(user["id"], DB_PATH).values())
    app.toggle(key="assistant_voice_enabled").set_value(False).run()
    prefs = get_user_preferences(user["id"], DB_PATH)
    assert not prefs["voice_replies"] and prefs["message_sounds"] and prefs["voice_alerts"]

    app.sidebar.radio[0].set_value("✓  Care Tasks").run()
    next(item for item in app.selectbox if item.label == "Task status").set_value("Completed").run()
    next(item for item in app.button if item.label == "Update status").click().run()
    assert list_care_tasks(user["id"], db_path=DB_PATH)[0]["status"] == "Completed"
    app.sidebar.radio[0].set_value("✉  Care Inbox").run()
    assert unread_conversations(user["id"], DB_PATH)
    next(item for item in app.button if item.label == "Mark displayed messages as read").click().run()
    assert not unread_conversations(user["id"], DB_PATH)
    assert not app.exception
    print("AUDIO_PERSISTENCE_TASK_UPDATE_AND_READ_RECEIPTS=PASS")

    safe_dietitian = {key: value for key, value in dietitian.items() if key != "password_hash"}
    clinical_app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    clinical_app.session_state["current_user"] = safe_dietitian
    clinical_app.run()
    for page in DIETITIAN_PAGES:
        clinical_app.sidebar.radio[0].set_value(page).run()
        errors = [str(exception.value) for exception in clinical_app.exception]
        if errors:
            raise AssertionError(f"{page}: {errors}")
        print(f"{page}: PASS")
    safe_admin = {key: value for key, value in admin.items() if key != "password_hash"}
    admin_app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    admin_app.session_state["current_user"] = safe_admin
    admin_app.run()
    for page in ADMIN_PAGES:
        admin_app.sidebar.radio[0].set_value(page).run()
        errors = [str(exception.value) for exception in admin_app.exception]
        if errors:
            raise AssertionError(f"{page}: {errors}")
        print(f"ADMIN · {page}: PASS")
    revoke_account_sessions(user["id"], DB_PATH)
    app.run()
    assert "current_user" not in app.session_state
    assert not app.exception
    print("SESSION_REVOCATION=PASS")
    print("STREAMLIT_CUSTOMER_DIETITIAN_AND_ADMIN_PAGES=PASS")


if __name__ == "__main__":
    main()
