from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from .constants import ACTIVITY_FACTORS, FOOD_DATA_PATH, GOAL_ADJUSTMENTS

NUMERIC_COLUMNS = [
    "calories", "protein_g", "fat_g", "carbs_g", "fiber_g",
    "sugar_g", "sodium_mg", "health_score", "healthy_rank_score",
]

FOOD_QUERY_ALIASES = {
    "baby back ribs": "pork ribs",
    "beef carpaccio": "beef",
    "beef tartare": "beef",
    "bibimbap": "rice beef vegetables",
    "breakfast burrito": "burrito egg",
    "chicken curry": "chicken",
    "chicken quesadilla": "chicken tortilla cheese",
    "clam chowder": "clam soup",
    "croque madame": "ham cheese bread egg",
    "deviled eggs": "egg",
    "edamame": "soybeans",
    "eggs benedict": "egg english muffin",
    "filet mignon": "beef steak",
    "fish and chips": "fish fried potato",
    "french fries": "potato fried",
    "fried calamari": "squid fried",
    "gyoza": "dumplings",
    "huevos rancheros": "egg beans tortilla",
    "macaroni and cheese": "macaroni cheese",
    "miso soup": "soy soup",
    "pad thai": "rice noodles",
    "peking duck": "duck",
    "pho": "noodle soup",
    "poutine": "french fries cheese",
    "prime rib": "beef ribs",
    "pulled pork sandwich": "pork sandwich",
    "ramen": "noodle soup",
    "samosa": "savory pastry",
    "sashimi": "raw fish",
    "shrimp and grits": "shrimp corn",
    "spaghetti bolognese": "spaghetti beef tomato",
    "spaghetti carbonara": "spaghetti egg cheese",
    "sushi": "rice fish",
    "takoyaki": "octopus",
    "tuna tartare": "tuna",
    "biryani": "biryani rice",
    "chicken biryani": "biryani chicken rice",
    "beef biryani": "biryani beef rice",
    "vegetable biryani": "biryani vegetable rice",
    "pulao": "pilaf rice",
    "pilau": "pilaf rice",
}

SEARCH_STOP_WORDS = {"and", "with", "the", "style", "dish", "food"}


@lru_cache(maxsize=2)
def load_food_data(path: str = str(FOOD_DATA_PATH)) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)
    aliases = {
        "name": "food_name", "category": "food_type", "protein": "protein_g",
        "fat": "fat_g", "carbohydrates": "carbs_g", "fiber": "fiber_g",
        "sugar": "sugar_g", "sodium": "sodium_mg",
    }
    frame = frame.rename(columns={key: value for key, value in aliases.items() if key in frame.columns})
    if "food_id" not in frame.columns:
        frame.insert(0, "food_id", np.arange(1, len(frame) + 1))
    if "healthy_rank_score" not in frame.columns:
        frame["healthy_rank_score"] = frame.get("health_score", 50)
    for column in NUMERIC_COLUMNS:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    frame["food_name"] = frame["food_name"].fillna("Unnamed food").astype(str)
    frame["food_type"] = frame["food_type"].fillna("Other").astype(str)
    return frame


def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, str]:
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("Weight and height must be greater than zero.")
    value = weight_kg / ((height_cm / 100) ** 2)
    if value < 18.5:
        category = "Underweight"
    elif value < 25:
        category = "Healthy range"
    elif value < 30:
        category = "Overweight"
    else:
        category = "Obesity range"
    return round(value, 1), category


def calculate_energy(profile: dict[str, Any]) -> dict[str, float]:
    weight = float(profile["weight_kg"])
    height = float(profile["height_cm"])
    age = int(profile["age"])
    if min(weight, height, age) <= 0:
        raise ValueError("Age, height and weight must be greater than zero.")
    sex = str(profile.get("biological_sex", "Male")).lower()
    constant = 5 if sex.startswith("m") else -161
    bmr = 10 * weight + 6.25 * height - 5 * age + constant
    activity = ACTIVITY_FACTORS.get(str(profile.get("activity")), 1.375)
    tdee = bmr * activity
    target = tdee + GOAL_ADJUSTMENTS.get(str(profile.get("goal")), 0)
    target = max(1200 if not sex.startswith("m") else 1500, min(4200, target))
    return {"bmr": round(bmr), "tdee": round(tdee), "target_calories": round(target)}


def macro_targets(calories: float, high_protein: bool = False) -> dict[str, float]:
    protein_pct = 0.30 if high_protein else 0.25
    fat_pct = 0.28
    carb_pct = 1 - protein_pct - fat_pct
    return {
        "protein_g": round(calories * protein_pct / 4),
        "carbs_g": round(calories * carb_pct / 4),
        "fat_g": round(calories * fat_pct / 9),
        "fiber_g": 32,
        "water_l": 2.6,
    }


def search_foods(frame: pd.DataFrame, query: str = "", category: str = "All",
                 max_calories: float | None = None, min_protein: float = 0,
                 sort_by: str = "healthy_rank_score", limit: int = 100) -> pd.DataFrame:
    result = frame
    if query.strip():
        result = result[result["food_name"].str.contains(query.strip(), case=False, na=False, regex=False)]
    if category != "All":
        result = result[result["food_type"] == category]
    if max_calories is not None:
        result = result[result["calories"] <= max_calories]
    result = result[result["protein_g"] >= min_protein]
    sort_column = sort_by if sort_by in result.columns else "healthy_rank_score"
    return result.sort_values(sort_column, ascending=False).head(limit).copy()


def search_foods_smart(frame: pd.DataFrame, query: str, limit: int = 30) -> pd.DataFrame:
    """Find close nutrition records for a predicted or typed dish name.

    Food-101 labels and the nutrition database do not share identical names, so this
    function ranks exact phrases first and then token/alias matches. Results remain
    suggestions that the user must confirm.
    """
    cleaned = " ".join(str(query).replace("_", " ").lower().split())
    if not cleaned:
        return frame.sort_values("healthy_rank_score", ascending=False).head(limit).copy()
    exact = frame[frame["food_name"].str.contains(cleaned, case=False, na=False, regex=False)]
    if not exact.empty:
        result = exact.copy()
        result.insert(len(result.columns), "match_score", 100.0)
        return result.sort_values(["match_score", "healthy_rank_score"], ascending=False).head(limit)

    expanded = FOOD_QUERY_ALIASES.get(cleaned, cleaned)
    tokens = [token for token in expanded.replace("/", " ").split() if len(token) > 2 and token not in SEARCH_STOP_WORDS]
    if not tokens:
        return frame.iloc[0:0].assign(match_score=pd.Series(dtype=float))
    names = frame["food_name"].str.lower()
    scores = pd.Series(0.0, index=frame.index)
    total_weight = 0.0
    for token in tokens:
        token_match = names.str.contains(rf"\b{re.escape(token)}", na=False, regex=True)
        frequency = max(1, int(token_match.sum()))
        weight = 1.0 / math.sqrt(frequency)
        scores += token_match.astype(float) * weight
        total_weight += weight
    matches = frame[scores > 0].copy()
    if matches.empty:
        return matches.assign(match_score=pd.Series(dtype=float))
    matches["match_score"] = (scores.loc[matches.index] / max(total_weight, 1e-9) * 100).round(0)
    return matches.sort_values(["match_score", "healthy_rank_score"], ascending=False).head(limit).copy()


def nutrition_totals(items: list[dict[str, Any]]) -> dict[str, float]:
    totals = {key: 0.0 for key in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"]}
    for item in items:
        servings = float(item.get("servings", 1))
        for key in totals:
            totals[key] += float(item.get(key, 0)) * servings
    return {key: round(value, 1) for key, value in totals.items()}


def dataset_quality(frame: pd.DataFrame) -> dict[str, Any]:
    missing = int(frame[NUMERIC_COLUMNS].isna().sum().sum())
    duplicates = int(frame.duplicated(subset=["food_name", "food_type"]).sum())
    return {
        "rows": len(frame),
        "categories": int(frame["food_type"].nunique()),
        "missing_numeric": missing,
        "duplicates": duplicates,
        "average_health_score": round(float(frame["health_score"].mean()), 1),
        "memory_mb": round(frame.memory_usage(deep=True).sum() / (1024 ** 2), 2),
    }


def health_score(food: dict[str, Any]) -> float:
    protein = min(float(food.get("protein_g", 0)) / 25, 1)
    fiber = min(float(food.get("fiber_g", 0)) / 10, 1)
    sugar_penalty = min(float(food.get("sugar_g", 0)) / 25, 1)
    sodium_penalty = min(float(food.get("sodium_mg", 0)) / 900, 1)
    value = 50 + 25 * protein + 25 * fiber - 15 * sugar_penalty - 15 * sodium_penalty
    return round(max(0, min(100, value)), 1)


def calorie_progress(consumed: float, target: float) -> float:
    if not math.isfinite(target) or target <= 0:
        return 0.0
    return max(0.0, min(1.0, consumed / target))
