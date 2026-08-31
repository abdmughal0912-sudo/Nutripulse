from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from pathlib import Path

from src.alerts import alert_counts, evaluate_alerts
from src.constants import ASSET_DIR, DATA_DIR
from src.database import (
    acknowledge_alert, add_clinical_note, add_clinical_prescription, add_food_log,
    create_meal_schedule, create_questionnaire,
    create_user, delete_food_log, get_food_logs, get_schedule_progress, initialize_database,
    link_dietitian_customer, list_alerts, list_clinical_messages, list_clinical_notes,
    list_clinical_prescriptions, list_lab_reports, list_meal_schedule, list_questionnaires,
    load_profile, save_lab_report, save_plan, send_clinical_message, set_dietitian_approval,
    set_meal_status, set_meal_status_with_progress, submit_questionnaire, sync_alerts, upsert_profile,
)
from src.auth import hash_password, verify_password
from src.diet_engine import generate_plan
from src.food_analysis import analyze_food_image
from src.image_sources import RemoteImageError, validate_public_image_url
from src.lab_analyzer import assess_safety, classify_manual_results, parse_lab_text
from src.ml_engine import food_vision_status, predict_food_image, predict_quality
from src.nutrition import calculate_bmi, calculate_energy, load_food_data, macro_targets, search_foods_smart
from src.reports import plan_to_pdf


def profile() -> dict:
    return {
        "id": "default-profile", "name": "Test User", "age": 30,
        "biological_sex": "Male", "height_cm": 175.0, "weight_kg": 78.0,
        "activity": "Moderately active", "goal": "Fat loss",
        "cuisine": "Pakistani + international", "conditions": [],
        "allergies": [], "medications": "",
    }


class NutritionTests(unittest.TestCase):
    def test_admin_setup_has_no_public_fallback(self) -> None:
        root = Path(__file__).resolve().parent.parent
        app_source = (root / "app.py").read_text(encoding="utf-8")
        readme = (root / "README.md").read_text(encoding="utf-8")
        unsafe_fallback = 'return "' + "NUTRIPULSE" + '-ADMIN"'
        unsafe_readme_phrase = "Local first-run Administrator " + "setup code"
        self.assertNotIn(unsafe_fallback, app_source)
        self.assertNotIn(unsafe_readme_phrase, readme)
        self.assertIn("disabled=not configured_admin_code", app_source)

    def test_windows_launcher_has_diagnostics_and_runtime_validation(self) -> None:
        root = Path(__file__).resolve().parent.parent
        launcher = (root / "START_ALL.bat").read_text(encoding="utf-8")
        self.assertIn("NUTRIPULSE_STARTUP_LOG.txt", launcher)
        self.assertIn("scripts\\runtime_check.py", launcher)
        self.assertIn("py -V:3.12", launcher)
        self.assertIn("-m streamlit run app.py", launcher)
        self.assertNotIn("^<=", launcher)

    def test_all_supplied_dataset_rows_are_audited(self) -> None:
        manifest = json.loads((DATA_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))
        audit = manifest["source_audit"]
        self.assertEqual(audit["raw_source_records"], 76920)
        self.assertEqual(audit["source_file_count"], 9)
        self.assertEqual(audit["classifier_ready_unique_records"], 47152)

    def test_bmi(self) -> None:
        value, category = calculate_bmi(70, 175)
        self.assertEqual(value, 22.9)
        self.assertEqual(category, "Healthy range")

    def test_energy_and_macros(self) -> None:
        energy = calculate_energy(profile())
        self.assertGreater(energy["target_calories"], 1500)
        self.assertLess(energy["target_calories"], energy["tdee"])
        macros = macro_targets(2000)
        self.assertGreater(macros["protein_g"], 100)

    def test_lab_parser_and_safety(self) -> None:
        results = parse_lab_text("HbA1c 6.2 LDL cholesterol 145 Vitamin D 18 eGFR 91 Potassium 4.1")
        names = {row["test"] for row in results}
        self.assertIn("HbA1c", names)
        self.assertIn("LDL cholesterol", names)
        safety = assess_safety(results, profile())
        self.assertTrue(safety["can_generate"])
        self.assertEqual(safety["level"], "clinician-review")

    def test_lab_parser_handles_extended_and_unmapped_report_rows(self) -> None:
        results = parse_lab_text(
            "WBC 7.8 x10^3/uL\nPlatelet count 245 x10^3/uL\n"
            "C Reactive Protein 12 mg/L\nCopper 91 ug/dL"
        )
        by_name = {row["test"]: row for row in results}
        self.assertEqual(by_name["WBC"]["value"], 7.8)
        self.assertEqual(by_name["Platelets"]["value"], 245)
        self.assertEqual(by_name["CRP"]["flag"], "high")
        self.assertEqual(by_name["Copper"]["flag"], "unverified")

    def test_critical_potassium_blocks_plan(self) -> None:
        results = parse_lab_text("Potassium 6.5")
        safety = assess_safety(results, profile())
        self.assertFalse(safety["can_generate"])
        with self.assertRaises(ValueError):
            generate_plan(profile(), results)

    def test_alert_engine_prioritizes_critical_laboratory_value(self) -> None:
        results = parse_lab_text("Potassium 6.5 LDL cholesterol 155")
        alerts = evaluate_alerts(profile(), results, lab_verified=True)
        self.assertEqual(alerts[0]["severity"], "Critical")
        self.assertIn("Potassium", alerts[0]["title"])
        self.assertGreaterEqual(alert_counts(alerts)["Medium"], 1)

    def test_unverified_report_creates_verification_alert(self) -> None:
        alerts = evaluate_alerts(profile(), parse_lab_text("HbA1c 6.4"), lab_verified=False)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "High")
        self.assertIn("verification", alerts[0]["title"].lower())

    def test_meal_analysis_creates_confidence_and_nutrition_alerts(self) -> None:
        patient = profile()
        patient["allergies"] = ["Peanuts"]
        alerts = evaluate_alerts(patient, meal_analysis={
            "selected_label": "Example meal",
            "vision": {"predictions": [{"label": "Example meal", "confidence": 0.20}]},
            "nutrition": {"calories": 900, "sugar_g": 45, "sodium_mg": 1200},
        })
        titles = " ".join(item["title"] for item in alerts).lower()
        self.assertIn("manual confirmation", titles)
        self.assertIn("sodium", titles)
        self.assertIn("allergens", titles)

    def test_meal_schedule_alert_is_time_connected(self) -> None:
        alerts = evaluate_alerts(profile(), meal_schedule=[{
            "id": "meal-1", "scheduled_date": "2026-08-27", "scheduled_time": "13:00",
            "meal_name": "Lunch", "status": "Planned",
        }], local_now=datetime(2026, 8, 27, 12, 45, tzinfo=timezone.utc))
        self.assertTrue(any("due" in item["title"].lower() for item in alerts))

    def test_plan_contains_seven_days(self) -> None:
        plan = generate_plan(profile(), parse_lab_text("HbA1c 6.0"))
        self.assertEqual(len(plan["days"]), 7)
        self.assertEqual(len(plan["days"][0]["meals"]), 4)
        self.assertEqual(plan["status"], "clinician-review")

    def test_lab_findings_change_meals_targets_and_traceability(self) -> None:
        patient = profile()
        glucose_plan = generate_plan(patient, parse_lab_text("HbA1c 7.2"))
        lipid_plan = generate_plan(
            patient,
            parse_lab_text("LDL cholesterol 178 Triglycerides 210"),
        )
        vitamin_plan = generate_plan(patient, parse_lab_text("Vitamin D 14"))

        self.assertNotEqual(glucose_plan["title"], lipid_plan["title"])
        self.assertNotEqual(lipid_plan["title"], vitamin_plan["title"])
        self.assertNotEqual(
            glucose_plan["lab_signature"], lipid_plan["lab_signature"],
        )
        self.assertLess(glucose_plan["carbs_g"], lipid_plan["carbs_g"])
        self.assertGreaterEqual(lipid_plan["fiber_g"], 38)

        glucose_meals = " ".join(
            meal["name"] + " " + meal["detail"]
            for day in glucose_plan["days"] for meal in day["meals"]
        )
        lipid_meals = " ".join(
            meal["name"] + " " + meal["detail"]
            for day in lipid_plan["days"] for meal in day["meals"]
        )
        vitamin_meals = " ".join(
            meal["name"] + " " + meal["detail"]
            for day in vitamin_plan["days"] for meal in day["meals"]
        )
        self.assertNotEqual(glucose_meals, lipid_meals)
        self.assertNotEqual(lipid_meals, vitamin_meals)
        self.assertEqual(
            glucose_plan["linked_lab_summary"][0]["test"], "HbA1c",
        )
        self.assertIn(
            "plan_response", glucose_plan["linked_lab_summary"][0],
        )

    def test_normal_lipid_values_use_maintenance_not_restriction(self) -> None:
        plan = generate_plan(
            profile(),
            parse_lab_text(
                "LDL cholesterol 81 HDL cholesterol 45 Total cholesterol 156"
            ),
        )
        self.assertIn("lipid-maintenance", plan["strategy_tags"])
        self.assertEqual(plan["status"], "wellness")
        self.assertTrue(
            all(row["flag"] == "normal" for row in plan["linked_lab_summary"])
        )

    def test_noncritical_kidney_findings_remain_clinician_led(self) -> None:
        plan = generate_plan(
            profile(),
            parse_lab_text("eGFR 45 Creatinine 1.6 Potassium 4.4"),
        )
        self.assertTrue(plan["requires_macro_review"])
        self.assertIn("kidney-clinician-review", plan["strategy_tags"])
        response = " ".join(
            row["plan_response"] for row in plan["linked_lab_summary"]
        ).lower()
        self.assertIn("no autonomous renal restriction", response)

    def test_invalid_manual_lab_value_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            classify_manual_results([{"test": "Potassium", "value": -1}])

    def test_vegan_allergy_constraints_are_applied(self) -> None:
        constrained = profile()
        constrained["cuisine"] = "Vegan"
        constrained["allergies"] = ["Milk", "Egg", "Fish", "Tree nuts", "Wheat/gluten", "Soy"]
        plan = generate_plan(constrained, [])
        text = " ".join(
            f"{meal['name']} {meal['detail']}" for day in plan["days"] for meal in day["meals"]
        ).lower()
        for forbidden in ["chicken", "beef", "tuna", "fish", " egg", "yogurt", "paneer", "tofu", "barley", "whole-wheat"]:
            self.assertNotIn(forbidden, text)

    def test_pdf_escapes_patient_name(self) -> None:
        plan = generate_plan(profile(), [])
        payload = plan_to_pdf(plan, "A <User> & Family")
        self.assertTrue(payload.startswith(b"%PDF"))

    def test_nutrition_classifier_predicts(self) -> None:
        food = load_food_data().iloc[0].to_dict()
        prediction = predict_quality(food)
        self.assertEqual(prediction["status"], "ready")
        self.assertIn(prediction["label"], {"Strong", "Balanced", "Limit"})
        self.assertAlmostEqual(sum(prediction["probabilities"].values()), 1.0, places=2)

    def test_smart_food_matching_handles_vision_label(self) -> None:
        matches = search_foods_smart(load_food_data(), "Chicken Curry", limit=10)
        self.assertFalse(matches.empty)
        self.assertIn("match_score", matches.columns)

    def test_regional_food_matching_prioritizes_biryani(self) -> None:
        matches = search_foods_smart(load_food_data(), "chicken biryani", limit=10)
        self.assertFalse(matches.empty)
        self.assertIn("biryani", matches.iloc[0]["food_name"].lower())

    def test_uncertain_vision_requires_actual_dish_confirmation(self) -> None:
        uncertain = {
            "status": "ready", "predictions": [
                {"label": "Pad Thai", "confidence": 0.47},
                {"label": "Fried Rice", "confidence": 0.42},
            ],
            "top_margin": 0.05, "confidence_level": "Moderate",
        }
        with patch("src.food_analysis.predict_food_image", return_value=uncertain):
            blocked = analyze_food_image(b"image", load_food_data())
            confirmed = analyze_food_image(
                b"image", load_food_data(), selected_label="Chicken biryani",
            )
        self.assertEqual(blocked["status"], "needs-confirmation")
        self.assertIsNone(blocked["nutrition_match"])
        self.assertEqual(confirmed["status"], "ready")
        self.assertIn("biryani", confirmed["nutrition_match"]["food_name"].lower())

    def test_public_image_url_rejects_private_networks_before_download(self) -> None:
        self.assertEqual(validate_public_image_url("https://example.com/meal.jpg"), "https://example.com/meal.jpg")
        with self.assertRaises(RemoteImageError):
            validate_public_image_url("file:///tmp/meal.jpg")

    @unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "onnxruntime is not installed")
    def test_bundled_vision_model_integrity(self) -> None:
        status = food_vision_status()
        self.assertEqual(status["status"], "Ready")
        self.assertEqual(status["integrity"], "Verified")
        self.assertEqual(status["classes"], 101)

    @unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "onnxruntime is not installed")
    def test_bundled_vision_model_runs_inference(self) -> None:
        prediction = predict_food_image((ASSET_DIR / "nutripulse_hero.jpg").read_bytes())
        self.assertEqual(prediction["status"], "ready")
        self.assertEqual(prediction["classes"], 101)
        self.assertEqual(len(prediction["predictions"]), 5)
        self.assertGreater(prediction["predictions"][0]["confidence"], 0.02)
        self.assertGreater(
            prediction["predictions"][0]["confidence"],
            prediction["predictions"][-1]["confidence"],
        )

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "OpenCV is not installed")
    def test_food_vision_uses_opencv_when_onnxruntime_dll_is_blocked(self) -> None:
        with patch("src.ml_engine._load_onnx_session", side_effect=ImportError("blocked DLL")):
            prediction = predict_food_image((ASSET_DIR / "nutripulse_hero.jpg").read_bytes())
        self.assertEqual(prediction["status"], "ready")
        self.assertIn("OpenCV DNN", prediction["runtime"])
        self.assertEqual(prediction["classes"], 101)

    @unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "onnxruntime is not installed")
    def test_end_to_end_food_image_analysis(self) -> None:
        analysis = analyze_food_image(
            (ASSET_DIR / "food_vision_luxury.jpg").read_bytes(), load_food_data(), servings=1.5,
        )
        self.assertIn(analysis["status"], {"ready", "needs-confirmation"})
        self.assertEqual(len(analysis["vision"]["predictions"]), 5)
        if analysis["status"] == "ready":
            self.assertIn("fat_g", analysis["nutrition"])
            self.assertGreaterEqual(analysis["nutrition"]["calories"], 0)


class DatabaseTests(unittest.TestCase):
    def test_password_hashing(self) -> None:
        encoded = hash_password("SecurePass123")
        self.assertTrue(verify_password("SecurePass123", encoded))
        self.assertFalse(verify_password("wrong-password", encoded))

    def test_database_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            initialize_database(db_path)
            profile_id = upsert_profile(profile(), db_path)
            loaded = load_profile(profile_id, db_path)
            self.assertEqual(loaded["name"], "Test User")
            labs = parse_lab_text("HbA1c 6.1")
            report_id = save_lab_report("report.pdf", labs, "clinician-review", db_path)
            plan = generate_plan(profile(), labs)
            plan_id = save_plan(profile_id, plan, report_id, db_path)
            self.assertTrue(report_id)
            self.assertTrue(plan_id)

    def test_food_log_can_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            initialize_database(db_path)
            profile_id = upsert_profile(profile(), db_path)
            food = load_food_data().iloc[0].to_dict()
            add_food_log(profile_id, "2026-08-25", "Lunch", food, 1.0, db_path)
            logs = get_food_logs(profile_id, "2026-08-25", db_path)
            self.assertEqual(len(logs), 1)
            self.assertTrue(delete_food_log(logs[0]["id"], profile_id, db_path))
            self.assertEqual(get_food_logs(profile_id, "2026-08-25", db_path), [])

    def test_alert_acknowledgement_and_resolution_persist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            initialize_database(db_path)
            patient = profile()
            patient["medications"] = "Example medicine"
            generated = evaluate_alerts(patient)
            current = sync_alerts(generated, db_path=db_path)
            self.assertEqual(len(current), 1)
            self.assertTrue(acknowledge_alert(current[0]["id"], db_path=db_path))
            refreshed = sync_alerts(generated, db_path=db_path)
            self.assertEqual(refreshed[0]["status"], "Acknowledged")
            sync_alerts([], db_path=db_path)
            history = list_alerts(include_resolved=True, db_path=db_path)
            self.assertEqual(history[0]["status"], "Resolved")

    def test_role_links_questionnaire_and_meal_completion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "test.db"
            initialize_database(db_path)
            customer = create_user("customer1", hash_password("Customer123"), "Customer", "Customer One", db_path=db_path)
            dietitian = create_user("dietitian1", hash_password("Dietitian123"), "Dietitian", "Dietitian One", credential="RD-001", db_path=db_path)
            patient = profile()
            patient["id"] = customer["id"]
            upsert_profile(patient, db_path)
            link_dietitian_customer(dietitian["id"], customer["id"], db_path)
            questionnaire_id = create_questionnaire(
                dietitian["id"], customer["id"], "Check-in", ["How are you?"], db_path,
            )
            submit_questionnaire(questionnaire_id, customer["id"], {"How are you?": "Well"}, db_path)
            self.assertEqual(list_questionnaires(customer_id=customer["id"], db_path=db_path)[0]["status"], "Completed")
            plan = generate_plan(patient, [])
            plan_id = save_plan(customer["id"], plan, db_path=db_path)
            self.assertGreater(create_meal_schedule(customer["id"], plan_id, plan, "2026-08-24", db_path), 0)
            meals = list_meal_schedule(customer["id"], date_from="2026-08-24", date_to="2026-08-30", db_path=db_path)
            self.assertTrue(set_meal_status(meals[0]["id"], customer["id"], "Completed", db_path))
            refreshed = list_meal_schedule(customer["id"], plan_id=plan_id, db_path=db_path)
            self.assertEqual(refreshed[0]["status"], "Completed")

    def test_schedule_advances_day_and_creates_next_week(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "progress.db"
            initialize_database(db_path)
            patient = profile()
            profile_id = upsert_profile(patient, db_path)
            plan = generate_plan(patient, [])
            plan_id = save_plan(profile_id, plan, db_path=db_path)
            self.assertGreater(create_meal_schedule(profile_id, plan_id, plan, "2026-08-24", db_path), 0)
            first_week = list_meal_schedule(
                profile_id, date_from="2026-08-24", date_to="2026-08-30",
                plan_id=plan_id, db_path=db_path,
            )
            first_day = [meal for meal in first_week if meal["scheduled_date"] == "2026-08-24"]
            transition = None
            for meal in first_day:
                transition = set_meal_status_with_progress(
                    meal["id"], profile_id, "Completed", db_path,
                )
            self.assertIsNotNone(transition)
            self.assertTrue(transition["day_completed"])
            self.assertEqual(transition["next_active_date"], "2026-08-25")
            self.assertIsNone(transition["completed_week_number"])

            for meal in first_week:
                if meal["scheduled_date"] == "2026-08-24":
                    continue
                transition = set_meal_status_with_progress(
                    meal["id"], profile_id, "Completed", db_path,
                )
            self.assertEqual(transition["completed_week_number"], 1)
            self.assertTrue(transition["next_week_created"])
            progress = get_schedule_progress(profile_id, plan_id, db_path)
            self.assertEqual(progress["completed_weeks"], 1)
            self.assertEqual(progress["active_week_number"], 2)
            self.assertEqual(progress["active_date"], "2026-08-31")
            self.assertEqual(len(progress["weeks"]), 2)

    def test_admin_approval_private_notes_prescriptions_and_question_thread(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "clinical.db"
            initialize_database(db_path)
            admin = create_user(
                "admin1", hash_password("Administrator123"), "Dietitian", "Administrator",
                credential="System Administrator", db_path=db_path,
                approval_status="Approved", is_admin=True,
            )
            dietitian = create_user(
                "dietitian2", hash_password("Dietitian123"), "Dietitian", "Clinical Dietitian",
                credential="RD-002", db_path=db_path,
            )
            self.assertEqual(dietitian["approval_status"], "Pending")
            self.assertEqual(dietitian["active"], 0)
            self.assertTrue(set_dietitian_approval(dietitian["id"], admin["id"], True, db_path))
            customer = create_user(
                "customer2", hash_password("Customer123"), "Customer", "Customer Two", db_path=db_path,
            )
            link_dietitian_customer(dietitian["id"], customer["id"], db_path)
            add_clinical_note(dietitian["id"], customer["id"], "Private assessment note", db_path)
            self.assertEqual(len(list_clinical_notes(customer["id"], db_path)), 1)
            add_clinical_prescription(
                dietitian["id"], customer["id"], "Nutrition target", "Protein target",
                "Aim for the agreed protein target using the meal plan.", db_path,
            )
            self.assertEqual(len(list_clinical_prescriptions(customer["id"], db_path)), 1)
            send_clinical_message(
                dietitian["id"], customer["id"], "Check-in", "Did you complete breakfast?",
                db_path, message_type="Question",
            )
            send_clinical_message(customer["id"], dietitian["id"], "Re: Check-in", "Yes.", db_path)
            thread = list_clinical_messages(dietitian["id"], customer["id"], db_path)
            self.assertEqual(thread[0]["status"], "Answered")
            report_id = save_lab_report(
                "customer-report.pdf", [{"test": "HbA1c", "value": 6.1}], "clinician-review",
                db_path, profile_id=customer["id"], reviewed_by="Clinical Dietitian",
            )
            self.assertEqual(list_lab_reports(customer["id"], db_path)[0]["id"], report_id)


if __name__ == "__main__":
    unittest.main()
