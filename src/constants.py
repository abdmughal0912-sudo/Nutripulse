import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def environment_path(name: str, default: Path) -> Path:
    """Return an absolute path that can be overridden by deployment settings."""
    configured = os.getenv(name, "").strip()
    return Path(configured).expanduser().resolve() if configured else default.resolve()


DATA_DIR = environment_path("NUTRIPULSE_DATA_DIR", ROOT_DIR / "data")
MODEL_DIR = environment_path("NUTRIPULSE_MODEL_DIR", ROOT_DIR / "models")
EXPORT_DIR = environment_path("NUTRIPULSE_EXPORT_DIR", ROOT_DIR / "exports")
ASSET_DIR = environment_path("NUTRIPULSE_ASSET_DIR", ROOT_DIR / "assets")
FOOD_DATA_PATH = environment_path("NUTRIPULSE_FOOD_DATA_PATH", DATA_DIR / "master_food_index.csv")
DATABASE_PATH = environment_path("NUTRIPULSE_DATABASE_PATH", DATA_DIR / "nutripulse.db")

APP_NAME = "NutriPulse AI"
APP_SUBTITLE = "Clinical-safe Nutrition Intelligence"
APP_VERSION = "4.3.0"

ACTIVITY_FACTORS = {
    "Sedentary": 1.20,
    "Lightly active": 1.375,
    "Moderately active": 1.55,
    "Very active": 1.725,
    "Athlete": 1.90,
}

GOAL_ADJUSTMENTS = {
    "Fat loss": -350,
    "Maintenance": 0,
    "Weight gain": 250,
    "Performance": 150,
}

SUPPORTED_LAB_TESTS = [
    "HbA1c", "Fasting glucose", "LDL cholesterol", "HDL cholesterol",
    "Triglycerides", "Vitamin D", "Vitamin B12", "Haemoglobin",
    "Ferritin", "eGFR", "Creatinine", "Potassium", "Sodium",
    "ALT", "Albumin", "Uric acid", "TSH",
    "Total cholesterol", "Random glucose", "Urea", "BUN", "AST", "ALP",
    "Total bilirubin", "CRP", "Calcium", "Magnesium", "Phosphate", "WBC",
    "Platelets", "Haematocrit", "MCV", "MCH", "MCHC", "Free T4", "Folate",
]

HIGH_RISK_NOTICE = (
    "This result requires review by a qualified doctor or dietitian. "
    "NutriPulse has stopped autonomous therapeutic planning."
)
