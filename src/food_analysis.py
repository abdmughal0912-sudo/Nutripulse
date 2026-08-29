from __future__ import annotations

from typing import Any

import pandas as pd

from .ml_engine import predict_food_image, predict_quality
from .nutrition import search_foods_smart


NUTRIENT_KEYS = ["calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "sodium_mg"]


def _scaled_nutrition(food: dict[str, Any], servings: float) -> dict[str, float]:
    return {
        key: round(float(food.get(key, 0) or 0) * servings, 1)
        for key in NUTRIENT_KEYS
    }


def _food_insights(nutrition: dict[str, float]) -> tuple[list[str], list[str]]:
    positives: list[str] = []
    watchouts: list[str] = []
    if nutrition["protein_g"] >= 20:
        positives.append("Protein-rich portion")
    if nutrition["fiber_g"] >= 6:
        positives.append("Good fibre contribution")
    if nutrition["sugar_g"] <= 8:
        positives.append("Lower estimated sugar")
    if nutrition["calories"] >= 800:
        watchouts.append("High estimated energy for one logged portion")
    if nutrition["fat_g"] >= 35:
        watchouts.append("High total-fat estimate; fat type is not available")
    if nutrition["sugar_g"] >= 25:
        watchouts.append("High estimated sugar")
    if nutrition["sodium_mg"] >= 800:
        watchouts.append("High estimated sodium")
    if nutrition["fiber_g"] < 3 and nutrition["calories"] >= 300:
        watchouts.append("Low estimated fibre relative to energy")
    if not positives:
        positives.append("Can fit a balanced pattern when portion and meal context are appropriate")
    return positives, watchouts


def analyze_food_image(
    image_bytes: bytes,
    frame: pd.DataFrame,
    *,
    servings: float = 1.0,
    selected_label: str | None = None,
) -> dict[str, Any]:
    """Recognize a dish and attach transparent database-based nutrition estimates."""
    servings = float(servings)
    if not 0.25 <= servings <= 10:
        raise ValueError("Servings must be between 0.25 and 10.")
    vision = predict_food_image(image_bytes)
    if vision.get("status") != "ready" or not vision.get("predictions"):
        return {"status": vision.get("status", "unavailable"), "message": vision.get("message", "Food vision unavailable."), "vision": vision}

    prediction_labels = [str(item["label"]) for item in vision["predictions"]]
    label = str(selected_label or prediction_labels[0]).strip()
    top_confidence = float(vision["predictions"][0].get("confidence", 0) or 0)
    top_margin = float(vision.get("top_margin", 0) or 0)
    uncertain = top_confidence < 0.60 or top_margin < 0.10
    if not selected_label and uncertain:
        return {
            "status": "needs-confirmation",
            "vision": vision,
            "candidate_label": prediction_labels[0],
            "nutrition_match": None,
            "message": (
                "The local model is not confident enough to identify this dish. It will not attach nutrition "
                "to an unrelated Food-101 label. Enter the actual dish name below (for example, chicken biryani)."
            ),
            "estimate_basis": "No calorie or nutrient estimate is produced until the dish is confirmed.",
        }
    matches = search_foods_smart(frame, label, limit=8)
    if matches.empty:
        return {
            "status": "needs-confirmation",
            "vision": vision,
            "selected_label": label,
            "nutrition_match": None,
            "message": "The dish was recognized, but no close nutrition-database record was found.",
            "estimate_basis": "Image classification only; enter or confirm nutrition manually.",
        }

    food = matches.iloc[0].to_dict()
    food = {key: (value.item() if hasattr(value, "item") else value) for key, value in food.items()}
    nutrition = _scaled_nutrition(food, servings)
    quality = predict_quality(food)
    positives, watchouts = _food_insights(nutrition)
    return {
        "status": "ready",
        "vision": vision,
        "selected_label": label,
        "identification_basis": "Human-confirmed dish name" if selected_label else "High-confidence Food-101 suggestion",
        "nutrition_match": food,
        "nutrition": nutrition,
        "servings": servings,
        "quality": quality,
        "health_score": round(float(food.get("healthy_rank_score", food.get("health_score", 0)) or 0), 1),
        "positives": positives,
        "watchouts": watchouts,
        "estimate_basis": (
            f"{('The dish name was confirmed by the user. ' if selected_label else '')}"
            "Nutrients are scaled from the closest database record, not measured from pixels. "
            "Confirm the dish, ingredients and portion before logging."
        ),
        "limitations": [
            "The model cannot see hidden oil, sauces, recipe quantities or preparation method.",
            "An image cannot confirm allergens, contamination or food safety.",
            "Health classification is educational and depends on the person's full diet and medical context.",
        ],
    }
