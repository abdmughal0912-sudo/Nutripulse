from __future__ import annotations

import importlib.util
import io
import os
import unittest

from fastapi.testclient import TestClient

from src.constants import APP_VERSION
from PIL import Image

from api import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def setUp(self) -> None:
        os.environ.pop("NUTRIPULSE_API_KEY", None)

    def test_root_health_and_openapi(self) -> None:
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["version"], APP_VERSION)
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertGreaterEqual(health.json()["food_records"], 8_000)
        self.assertEqual(health.json()["raw_source_records"], 76_920)
        schema = self.client.get("/openapi.json")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("/api/v1/vision/predict", schema.json()["paths"])
        self.assertIn("/api/v1/vision/analyze", schema.json()["paths"])
        self.assertIn("/api/v1/vision/analyze-url", schema.json()["paths"])
        self.assertIn("/api/v1/alerts/evaluate", schema.json()["paths"])
        self.assertIn("/api/v1/assistant/ask", schema.json()["paths"])
        self.assertIn("/api/v1/diary/vision-url", schema.json()["paths"])
        self.assertIn("/api/v1/schedule/{meal_id}/status", schema.json()["paths"])
        self.assertEqual(self.client.get("/favicon.ico").status_code, 200)

    def test_food_search_and_classifier(self) -> None:
        search = self.client.get("/api/v1/foods/search", params={"q": "apple", "limit": 5})
        self.assertEqual(search.status_code, 200)
        self.assertGreater(search.json()["count"], 0)
        self.assertLessEqual(search.json()["count"], 5)
        prediction = self.client.post("/api/v1/classifier/predict", json={
            "food_name": "Test meal", "food_type": "Other", "calories": 320,
            "protein_g": 18, "fat_g": 9, "carbs_g": 42, "fiber_g": 8,
            "sugar_g": 5, "sodium_mg": 260,
        })
        self.assertEqual(prediction.status_code, 200)
        self.assertIn(prediction.json()["label"], {"Strong", "Balanced", "Limit"})

    def test_lab_analysis_and_diet_plan(self) -> None:
        profile = {
            "name": "API Test", "age": 31, "biological_sex": "Female",
            "height_cm": 165, "weight_kg": 68, "activity": "Moderately active",
            "goal": "Maintenance", "cuisine": "Pakistani + international",
            "conditions": [], "allergies": [], "medications": "",
        }
        labs = self.client.post("/api/v1/labs/analyze", json={
            "profile": profile,
            "values": [{"test": "HbA1c", "value": 6.1, "unit": "%"}],
        })
        self.assertEqual(labs.status_code, 200)
        self.assertEqual(labs.json()["safety"]["level"], "clinician-review")
        plan = self.client.post("/api/v1/diet/plan", json={
            "profile": profile,
            "labs": [{"test": "HbA1c", "value": 6.1, "unit": "%"}],
        })
        self.assertEqual(plan.status_code, 200)
        self.assertEqual(len(plan.json()["days"]), 7)

    def test_api_key_gate(self) -> None:
        os.environ["NUTRIPULSE_API_KEY"] = "test-secret"
        denied = self.client.get("/api/v1/foods/search")
        self.assertEqual(denied.status_code, 401)
        allowed = self.client.get("/api/v1/foods/search", headers={"X-API-Key": "test-secret"})
        self.assertEqual(allowed.status_code, 200)

    def test_alert_evaluation_endpoint(self) -> None:
        response = self.client.post("/api/v1/alerts/evaluate", json={
            "profile": {
                "name": "Alert Test", "age": 30, "biological_sex": "Male",
                "height_cm": 175, "weight_kg": 75, "activity": "Moderately active",
                "goal": "Maintenance", "cuisine": "Pakistani + international",
                "conditions": [], "allergies": [], "medications": "",
            },
            "labs": [{"test": "Potassium", "value": 6.5, "unit": "mmol/L"}],
            "lab_verified": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["Critical"], 1)
        self.assertIn("urgent", response.json()["alerts"][0]["title"].lower())

    def test_schedule_api_includes_day_and_week_progress(self) -> None:
        response = self.client.get(
            "/api/v1/schedule", params={"profile_id": "api-progress-empty"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["progress"]["days"], [])
        self.assertEqual(payload["progress"]["weeks"], [])
        self.assertIn("active_week_number", payload["progress"])

    def test_grounded_assistant_endpoint(self) -> None:
        response = self.client.post("/api/v1/assistant/ask", json={
            "question": "How does my calorie target work?",
            "profile": {
                "name": "Assistant Test", "age": 30, "biological_sex": "Male",
                "height_cm": 175, "weight_kg": 75, "activity": "Moderately active",
                "goal": "Maintenance", "cuisine": "Pakistani + international",
                "conditions": [], "allergies": [], "medications": "",
            },
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("goal", response.json()["answer"].lower())

    def test_trusted_source_catalog_and_ssrf_block(self) -> None:
        sources = self.client.get("/api/v1/web/sources")
        self.assertEqual(sources.status_code, 200)
        self.assertGreaterEqual(sources.json()["count"], 4)
        blocked = self.client.post("/api/v1/web/scrape", json={"url": "http://127.0.0.1/private"})
        self.assertEqual(blocked.status_code, 422)
        blocked_extract = self.client.post("/api/v1/web/extract", json={"url": "http://127.0.0.1/private"})
        self.assertEqual(blocked_extract.status_code, 422)
        blocked_image = self.client.post("/api/v1/vision/analyze-url", json={"url": "http://127.0.0.1/meal.jpg"})
        self.assertEqual(blocked_image.status_code, 422)

    @unittest.skipUnless(importlib.util.find_spec("onnxruntime"), "onnxruntime is not installed")
    def test_vision_upload(self) -> None:
        image = Image.new("RGB", (320, 260), (180, 90, 40))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        response = self.client.post(
            "/api/v1/vision/predict",
            files={"image": ("meal.jpg", buffer.getvalue(), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["predictions"]), 5)
        analysis = self.client.post(
            "/api/v1/vision/analyze",
            files={"image": ("meal.jpg", buffer.getvalue(), "image/jpeg")},
            data={"servings": "1.5"},
        )
        self.assertEqual(analysis.status_code, 200)
        self.assertIn(analysis.json()["status"], {"ready", "needs-confirmation"})


if __name__ == "__main__":
    unittest.main()
