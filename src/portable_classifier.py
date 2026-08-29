"""Pure-Python inference for NutriPulse portable random-forest artifacts."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=2)
def load_portable_forest(path_text: str, modified_ns: int) -> dict[str, Any]:
    del modified_ns
    path = Path(path_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != "nutripulse-portable-forest-v1":
        raise ValueError("Unsupported portable classifier format.")
    if not payload.get("trees") or not payload.get("classes"):
        raise ValueError("Portable classifier is incomplete.")
    return payload


def feature_vector(food: dict[str, Any]) -> dict[str, float]:
    base_names = ["calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "sodium_mg"]
    values: dict[str, float] = {}
    for name in base_names:
        try:
            value = float(food.get(name, 0) or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric.") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a finite, non-negative value.")
        values[name] = value
    denominator = max(values["calories"], 30.0)
    values.update({
        "protein_density": values["protein_g"] * 100 / denominator,
        "fiber_density": values["fiber_g"] * 100 / denominator,
        "sugar_density": values["sugar_g"] * 100 / denominator,
        "sodium_density": values["sodium_mg"] * 100 / denominator,
    })
    return values


def predict_portable(path: Path, food: dict[str, Any]) -> tuple[str, dict[str, float]]:
    model = load_portable_forest(str(path), path.stat().st_mtime_ns)
    features = feature_vector(food)
    vector = [features[name] for name in model["features"]]
    classes = [str(item) for item in model["classes"]]
    totals = [0.0 for _ in classes]
    for tree in model["trees"]:
        node = 0
        while int(tree["children_left"][node]) != -1:
            feature_index = int(tree["feature"][node])
            if vector[feature_index] <= float(tree["threshold"][node]):
                node = int(tree["children_left"][node])
            else:
                node = int(tree["children_right"][node])
        votes = [float(item) for item in tree["value"][node]]
        vote_sum = sum(votes)
        if vote_sum > 0:
            for index, vote in enumerate(votes):
                totals[index] += vote / vote_sum
    tree_count = max(1, len(model["trees"]))
    probabilities = [value / tree_count for value in totals]
    probability_sum = sum(probabilities)
    if probability_sum <= 0:
        probabilities = [1 / len(classes) for _ in classes]
    else:
        probabilities = [value / probability_sum for value in probabilities]
    best_index = max(range(len(classes)), key=probabilities.__getitem__)
    return classes[best_index], {
        name: round(float(value), 4) for name, value in zip(classes, probabilities)
    }
