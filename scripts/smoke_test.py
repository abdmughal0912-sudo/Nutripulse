from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.alerts import alert_counts, evaluate_alerts
from src.database import initialize_database, load_profile, save_lab_report, save_plan, sync_alerts, upsert_profile
from src.diet_engine import generate_plan, grocery_list
from src.lab_analyzer import assess_safety, classify_manual_results, parse_lab_text
from src.ml_engine import food_vision_status, model_status, predict_food_image, predict_quality
from src.nutrition import dataset_quality, load_food_data
from src.reports import plan_to_csv, plan_to_json, plan_to_pdf


def sample_profile() -> dict:
    return {
        "id": "smoke-profile", "name": "Smoke <Test> & User", "age": 34,
        "biological_sex": "Female", "height_cm": 165.0, "weight_kg": 68.0,
        "activity": "Moderately active", "goal": "Maintenance", "cuisine": "Vegan",
        "conditions": ["Hypertension"],
        "allergies": ["Milk", "Egg", "Fish", "Tree nuts", "Wheat/gluten", "Soy"],
        "medications": "Recorded for clinician review only",
    }


def main() -> None:
    required = [
        ROOT / "app.py", ROOT / "api.py", ROOT / "requirements.txt", ROOT / "Dockerfile",
        ROOT / "docker-compose.yml", ROOT / "data" / "master_food_index.csv",
        ROOT / "data" / "food_safety_registry.csv", ROOT / "data" / "dataset_manifest.json",
        ROOT / "models" / "nutrition_quality_portable.json",
        ROOT / "models" / "food_classifier.onnx", ROOT / "models" / "food_labels.json",
        ROOT / "src" / "web_insights.py", ROOT / "src" / "alerts.py", ROOT / "START_ALL.bat",
        ROOT / "assets" / "nutripulse_hero.jpg", ROOT / "assets" / "lab_nutrition.jpg",
        ROOT / "assets" / "web_insights.jpg",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    assert not missing, f"Missing deployment files: {missing}"

    frame = load_food_data()
    quality = dataset_quality(frame)
    assert quality["rows"] >= 45_000
    assert quality["missing_numeric"] == 0
    manifest = json.loads((ROOT / "data" / "dataset_manifest.json").read_text(encoding="utf-8"))
    source_audit = manifest["source_audit"]
    assert source_audit["raw_source_records"] == 76_920
    assert source_audit["food_related_source_records"] == 70_920
    assert source_audit["classifier_ready_unique_records"] == quality["rows"]

    parsed = parse_lab_text("HbA1c 6.1 LDL cholesterol 142 Vitamin D 19 eGFR 92 Potassium 4.2")
    safety = assess_safety(parsed, sample_profile())
    assert safety["level"] == "clinician-review"
    assert classify_manual_results([{"test": "HbA1c", "value": 6.1}])[0]["flag"] == "high"
    critical_alerts = evaluate_alerts(sample_profile(), parse_lab_text("Potassium 6.5"))
    assert alert_counts(critical_alerts)["Critical"] == 1

    plan = generate_plan(sample_profile(), parsed)
    assert len(plan["days"]) == 7
    combined = " ".join(
        f"{meal['name']} {meal['detail']}" for day in plan["days"] for meal in day["meals"]
    ).lower()
    for forbidden in ["chicken", "beef", "tuna", "fish", " egg", "yogurt", "paneer", "tofu", "barley", "whole-wheat"]:
        assert forbidden not in combined, f"Dietary constraint leak: {forbidden}"
    groceries = grocery_list(plan)
    assert groceries

    pdf = plan_to_pdf(plan, sample_profile()["name"])
    assert pdf.startswith(b"%PDF") and len(pdf) > 4_000
    assert plan_to_csv(plan).startswith(b"Day,Time,Meal")
    assert json.loads(plan_to_json(plan))["cuisine"] == "Vegan"

    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "smoke.db"
        initialize_database(db_path)
        profile_id = upsert_profile(sample_profile(), db_path)
        report_id = save_lab_report("smoke.pdf", parsed, safety["level"], db_path)
        plan_id = save_plan(profile_id, plan, report_id, db_path)
        stored_alerts = sync_alerts(critical_alerts, profile_id, db_path)
        assert load_profile(profile_id, db_path)["name"] == sample_profile()["name"]
        assert report_id and plan_id and stored_alerts[0]["severity"] == "Critical"

    status = model_status()
    prediction = predict_quality(frame.iloc[0].to_dict())
    assert status["status"] == "Ready"
    assert prediction["status"] == "ready"

    vision_status = food_vision_status()
    assert vision_status["status"] == "Ready", vision_status
    assert vision_status["integrity"] == "Verified"
    vision_prediction = predict_food_image((ROOT / "assets" / "nutripulse_hero.jpg").read_bytes())
    assert vision_prediction["status"] == "ready", vision_prediction
    assert len(vision_prediction["predictions"]) == 5
    assert vision_prediction["predictions"][0]["confidence"] > 0.02, "Food Vision output is near-uniform"

    print(json.dumps({
        "raw_source_records": source_audit["raw_source_records"],
        "food_related_source_records": source_audit["food_related_source_records"],
        "classifier_ready_unique_records": quality["rows"], "plan_days": len(plan["days"]),
        "pdf_bytes": len(pdf), "model_status": status["status"],
        "vision_status": vision_status["status"], "vision_classes": vision_prediction["classes"],
        "critical_alerts": alert_counts(critical_alerts)["Critical"],
    }, indent=2))
    print("NUTRIPULSE_SMOKE_TEST=PASS")


if __name__ == "__main__":
    main()
