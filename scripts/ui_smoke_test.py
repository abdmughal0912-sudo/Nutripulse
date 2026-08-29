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
    save_plan, upsert_profile,
)
from src.diet_engine import generate_plan

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
]

ADMIN_PAGES = [
    *DIETITIAN_PAGES,
    "⚙  Administrator Governance",
    "⌘  Dataset & Model Audit",
]


def main() -> None:
    initialize_database(DB_PATH)
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
    print("STREAMLIT_CUSTOMER_DIETITIAN_AND_ADMIN_PAGES=PASS")


if __name__ == "__main__":
    main()
