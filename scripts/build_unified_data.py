"""Build NutriPulse's unified food, safety, benchmark, and portable ML artifacts.

This script is an offline build tool. The generated application runtime does not
import scikit-learn or SciPy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


FEATURES = ["calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "sodium_mg"]
LABELS = ["Strong", "Balanced", "Limit"]

SOURCE_SPECS = [
    ("comprehensive_foods_usda(1).csv", "food_name", "Food", "Nutrition index + classifier", True),
    ("healthy_foods_database(1).csv", "food_name", "Food", "Nutrition index + classifier", True),
    ("food_menu_nutrition_dataset(1).csv", "item_name", "Menu food", "Nutrition index + classifier", True),
    ("FOOD-DATA-GROUP1(1).csv", "food", "Food", "Nutrition index + classifier", True),
    ("fastfood(1).csv", "item", "Restaurant food", "Nutrition index + classifier", True),
    ("foods_health_scores_allergens(1).csv", "product_name", "Packaged food", "Nutrition index + safety", True),
    ("foods_dietary_restrictions(1).csv", "product_name", "Safety product", "Allergen/restriction registry", False),
    ("foods_allergens(1).csv", "product_name", "Safety product", "Declared-allergen registry", False),
    ("healthy_diet_calorie_intake(1).csv", "Person_ID", "Person benchmark", "Population intake benchmarks", False),
]


def clean_number(series: pd.Series, *, multiplier: float = 1.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).clip(lower=0) * multiplier


def score_food(frame: pd.DataFrame) -> pd.Series:
    calories = frame["calories"].clip(0, 1600)
    protein = frame["protein_g"].clip(0, 80)
    fiber = frame["fiber_g"].clip(0, 40)
    sugar = frame["sugar_g"].clip(0, 120)
    sodium = frame["sodium_mg"].clip(0, 4000)
    fat = frame["fat_g"].clip(0, 120)
    score = (
        55
        + protein.mul(0.65).clip(upper=16)
        + fiber.mul(2.1).clip(upper=22)
        - sugar.mul(0.55).clip(upper=25)
        - sodium.sub(250).clip(lower=0).mul(0.012).clip(upper=25)
        - calories.sub(550).clip(lower=0).mul(0.035).clip(upper=22)
        - fat.sub(35).clip(lower=0).mul(0.3).clip(upper=15)
    )
    return score.clip(0, 100).round(1)


def normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def build_source_registry(source_dir: Path) -> tuple[pd.DataFrame, dict]:
    """Account for every supplied row without mislabelling people or safety rows as foods."""
    frames: list[pd.DataFrame] = []
    by_file: list[dict] = []
    running_id = 1
    for file_name, name_column, record_type, purpose, classifier_candidate in SOURCE_SPECS:
        source = pd.read_csv(source_dir / file_name, low_memory=False)
        names = source.get(name_column, pd.Series("", index=source.index)).fillna("").astype(str).str.strip()
        current = pd.DataFrame({
            "source_record_id": [f"SRC{index:07d}" for index in range(running_id, running_id + len(source))],
            "source_file": file_name,
            "source_row": source.index + 2,
            "record_type": record_type,
            "record_name": names,
            "integration_purpose": purpose,
            "classifier_candidate": classifier_candidate,
            "integration_status": "Integrated",
        })
        frames.append(current)
        by_file.append({
            "source_file": file_name,
            "raw_records": int(len(source)),
            "record_type": record_type,
            "integration_purpose": purpose,
            "classifier_candidate": classifier_candidate,
        })
        running_id += len(source)
    registry = pd.concat(frames, ignore_index=True)
    summary = {
        "raw_source_records": int(len(registry)),
        "food_related_source_records": int((registry["record_type"] != "Person benchmark").sum()),
        "nutrition_candidate_input_records": int(registry["classifier_candidate"].sum()),
        "safety_source_records": int((registry["record_type"] == "Safety product").sum()),
        "benchmark_source_records": int((registry["record_type"] == "Person benchmark").sum()),
        "source_file_count": int(registry["source_file"].nunique()),
        "by_file": by_file,
    }
    return registry, summary


def base_frame(name: pd.Series, food_type: pd.Series, source: str, **columns: pd.Series) -> pd.DataFrame:
    result = pd.DataFrame({
        "food_name": name.fillna("").astype(str).str.strip(),
        "food_type": food_type.fillna("Other").astype(str).str.strip().replace("", "Other"),
        "source_dataset": source,
    })
    for feature in FEATURES:
        result[feature] = clean_number(columns.get(feature, pd.Series(0, index=result.index)))
    return result[result["food_name"].str.len().between(2, 180)].copy()


def build_food_index(source_dir: Path) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []

    usda = pd.read_csv(source_dir / "comprehensive_foods_usda(1).csv", low_memory=False)
    part = base_frame(
        usda["food_name"], usda["food_type"], "USDA comprehensive",
        calories=usda["calories"], protein_g=usda["protein_g"], fat_g=usda["fat_g"],
        carbs_g=usda["carbs_g"], fiber_g=usda["fiber_g"], sugar_g=usda["sugar_g"],
        sodium_mg=usda["sodium_mg"],
    )
    part["source_health_score"] = clean_number(usda.loc[part.index, "health_score"]).clip(0, 100)
    parts.append(part)

    healthy = pd.read_csv(source_dir / "healthy_foods_database(1).csv", low_memory=False)
    part = base_frame(
        healthy["food_name"], healthy["food_type"], "Healthy foods database",
        calories=healthy["calories"], protein_g=healthy["protein_g"], fat_g=healthy["fat_g"],
        carbs_g=healthy["carbs_g"], fiber_g=healthy["fiber_g"], sugar_g=healthy["sugar_g"],
        sodium_mg=healthy["sodium_mg"],
    )
    part["source_health_score"] = clean_number(healthy.loc[part.index, "health_score"]).clip(0, 100)
    parts.append(part)

    menu = pd.read_csv(source_dir / "food_menu_nutrition_dataset(1).csv", low_memory=False)
    menu_name = (
        menu["brand_name"].fillna("").astype(str).str.strip() + " — "
        + menu["item_name"].fillna("").astype(str).str.strip() + " ("
        + menu["country"].fillna("Global").astype(str).str.strip() + ")"
    )
    parts.append(base_frame(
        menu_name, menu["item_category"], "Global menu nutrition",
        calories=menu["calories"], protein_g=menu["protein_g"], fat_g=menu["total_fat_g"],
        carbs_g=menu["total_carbs_g"], sugar_g=menu["sugars_g"], sodium_mg=menu["sodium_mg"],
    ))

    dense = pd.read_csv(source_dir / "FOOD-DATA-GROUP1(1).csv", low_memory=False)
    parts.append(base_frame(
        dense["food"], pd.Series("Nutrition density", index=dense.index), "Food nutrient density",
        calories=dense["Caloric Value"], protein_g=dense["Protein"], fat_g=dense["Fat"],
        carbs_g=dense["Carbohydrates"], fiber_g=dense["Dietary Fiber"], sugar_g=dense["Sugars"],
        sodium_mg=clean_number(dense["Sodium"], multiplier=1000),
    ))

    fast = pd.read_csv(source_dir / "fastfood(1).csv", low_memory=False)
    parts.append(base_frame(
        fast["restaurant"].fillna("") + " — " + fast["item"].fillna(""),
        pd.Series("Restaurant / fast food", index=fast.index), "Fast-food nutrition",
        calories=fast["calories"], protein_g=fast["protein"], fat_g=fast["total_fat"],
        carbs_g=fast["total_carb"], fiber_g=fast["fiber"], sugar_g=fast["sugar"],
        sodium_mg=fast["sodium"],
    ))

    packaged = pd.read_csv(source_dir / "foods_health_scores_allergens(1).csv", low_memory=False)
    packaged_name = packaged["product_name"].fillna("").astype(str)
    branded = packaged["brands"].fillna("").astype(str)
    packaged_name = packaged_name.where(branded.str.len().eq(0), branded + " — " + packaged_name)
    part = base_frame(
        packaged_name, packaged["food_type"], "Packaged food + health score",
        calories=packaged["energy_kcal"], protein_g=packaged["proteins_100g"], fat_g=packaged["fat_100g"],
        carbs_g=packaged["carbs_100g"], fiber_g=packaged["fiber_100g"], sugar_g=packaged["sugars_100g"],
        sodium_mg=clean_number(packaged["sodium_100g"], multiplier=1000),
    )
    grade_score = packaged.loc[part.index, "nutriscore_grade"].astype(str).str.upper().map(
        {"A": 90, "B": 75, "C": 60, "D": 40, "E": 20}
    ).fillna(0)
    part["source_health_score"] = grade_score
    parts.append(part)

    combined = pd.concat(parts, ignore_index=True)
    combined[FEATURES] = combined[FEATURES].replace([np.inf, -np.inf], 0).fillna(0).round(3)
    combined = combined[
        combined["calories"].between(0, 3000)
        & combined["protein_g"].between(0, 400)
        & combined["fat_g"].between(0, 400)
        & combined["carbs_g"].between(0, 800)
        & combined["sodium_mg"].between(0, 50000)
    ].copy()
    combined["food_key"] = combined["food_name"].map(normalized_key)
    combined["dedupe_key"] = (
        combined["food_key"] + "|" + combined["calories"].round(1).astype(str)
        + "|" + combined["food_type"].map(normalized_key)
    )
    combined = combined.sort_values(
        ["dedupe_key", "source_health_score", "fiber_g", "protein_g"],
        ascending=[True, False, False, False],
    ).drop_duplicates("dedupe_key", keep="first")
    derived = score_food(combined)
    source_score = combined.get("source_health_score", pd.Series(0, index=combined.index))
    combined["health_score"] = np.where(source_score.gt(0), source_score.mul(.55) + derived.mul(.45), derived)
    combined["health_score"] = pd.Series(combined["health_score"], index=combined.index).clip(0, 100).round(1)
    combined["quality_label"] = pd.cut(
        combined["health_score"], bins=[-math.inf, 44.999, 69.999, math.inf],
        labels=["Limit", "Balanced", "Strong"],
    ).astype(str)
    combined = combined.sort_values(["health_score", "food_name"], ascending=[False, True]).reset_index(drop=True)
    combined.insert(0, "food_id", [f"NP{index:06d}" for index in range(1, len(combined) + 1)])
    return combined[["food_id", "food_name", "food_type", *FEATURES, "health_score", "quality_label", "source_dataset"]]


def build_safety_registry(source_dir: Path) -> pd.DataFrame:
    restrictions = pd.read_csv(source_dir / "foods_dietary_restrictions(1).csv", low_memory=False)
    allergens = pd.read_csv(source_dir / "foods_allergens(1).csv", low_memory=False)
    keys = ["contains_gluten", "contains_dairy", "contains_nuts", "contains_soy", "contains_eggs", "contains_fish"]
    frames = []
    for source, data in [("Dietary restrictions", restrictions), ("Declared allergens", allergens)]:
        current = pd.DataFrame({
            "product_name": data["product_name"].fillna("").astype(str).str.strip(),
            "brand": data.get("brands", pd.Series("", index=data.index)).fillna("").astype(str).str.strip(),
            "declared_allergens": data.get("allergens", pd.Series("", index=data.index)).fillna("").astype(str),
            "source_dataset": source,
        })
        for key in keys:
            current[key] = data.get(key, False).fillna(False).astype(bool)
        frames.append(current[current["product_name"].str.len().ge(2)])
    registry = pd.concat(frames, ignore_index=True)
    registry["key"] = registry["brand"].map(normalized_key) + "|" + registry["product_name"].map(normalized_key)
    grouped = registry.groupby("key", as_index=False).agg({
        "product_name": "first", "brand": "first", "declared_allergens": lambda s: ", ".join(sorted({v for v in s if v})),
        **{key: "max" for key in keys}, "source_dataset": lambda s: " + ".join(sorted(set(s))),
    })
    return grouped.drop(columns=["key"]).sort_values(["brand", "product_name"]).reset_index(drop=True)


def build_benchmarks(source_dir: Path) -> dict:
    data = pd.read_csv(source_dir / "healthy_diet_calorie_intake(1).csv", low_memory=False)
    numeric = [
        "Daily_Calorie_Requirement", "Daily_Calorie_Consumed", "Protein_Intake_g",
        "Carbohydrate_Intake_g", "Fat_Intake_g", "Water_Intake_Liters",
    ]
    summary = {}
    for column in numeric:
        values = clean_number(data[column])
        summary[column] = {
            "median": round(float(values.median()), 2),
            "p25": round(float(values.quantile(.25)), 2),
            "p75": round(float(values.quantile(.75)), 2),
        }
    return {
        "records": int(len(data)), "source": "healthy_diet_calorie_intake(1).csv",
        "numeric_benchmarks": summary,
        "diet_type_counts": data["Diet_Type"].fillna("Unknown").value_counts().to_dict(),
        "health_status_counts": data["Health_Status"].fillna("Unknown").value_counts().to_dict(),
    }


def export_forest(model: object, feature_names: list[str]) -> dict:
    trees = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        trees.append({
            "children_left": tree.children_left.astype(int).tolist(),
            "children_right": tree.children_right.astype(int).tolist(),
            "feature": tree.feature.astype(int).tolist(),
            "threshold": np.round(tree.threshold, 7).tolist(),
            "value": np.round(tree.value[:, 0, :], 7).tolist(),
        })
    return {
        "format": "nutripulse-portable-forest-v1", "features": feature_names,
        "classes": [str(item) for item in model.classes_], "trees": trees,
    }


def train_portable_model(food_index: pd.DataFrame, random_state: int = 42) -> tuple[dict, dict]:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split

    feature_names = FEATURES + ["protein_density", "fiber_density", "sugar_density", "sodium_density"]
    x = food_index[FEATURES].astype(float).copy()
    denominator = x["calories"].clip(lower=30)
    x["protein_density"] = x["protein_g"] * 100 / denominator
    x["fiber_density"] = x["fiber_g"] * 100 / denominator
    x["sugar_density"] = x["sugar_g"] * 100 / denominator
    x["sodium_density"] = x["sodium_mg"] * 100 / denominator
    y = food_index["quality_label"].astype(str)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=.2, random_state=random_state, stratify=y,
    )
    model = RandomForestClassifier(
        n_estimators=72, max_depth=12, min_samples_leaf=4,
        class_weight="balanced_subsample", n_jobs=-1, random_state=random_state,
    )
    model.fit(x_train, y_train)
    predicted = model.predict(x_test)
    probabilities = model.predict_proba(x_test)
    metrics = {
        "model": "Portable Random Forest", "format": "nutripulse-portable-forest-v1",
        "samples": int(len(food_index)), "train_samples": int(len(x_train)), "test_samples": int(len(x_test)),
        "accuracy": round(float(accuracy_score(y_test, predicted)), 6),
        "macro_f1": round(float(f1_score(y_test, predicted, average="macro")), 6),
        "classes": list(model.classes_), "features": feature_names,
        "average_confidence": round(float(np.max(probabilities, axis=1).mean()), 6),
        "random_state": random_state,
        "runtime_dependencies": ["Python standard library"],
        "training_dependencies": ["pandas", "numpy", "scikit-learn"],
        "clinical_scope": "Educational food-quality classification; not diagnosis or dietary prescription.",
    }
    portable = export_forest(model, feature_names)
    portable["metadata"] = metrics
    return portable, metrics


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument(
        "--audit-only", action="store_true",
        help="Refresh the all-source row registry and manifest audit without retraining the model.",
    )
    args = parser.parse_args()
    data_dir = args.project_dir / "data"
    model_dir = args.project_dir / "models"
    data_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    source_registry, source_audit = build_source_registry(args.source_dir)
    source_registry_path = data_dir / "source_record_registry.csv"
    if args.audit_only:
        source_registry.to_csv(source_registry_path, index=False)
        manifest_path = data_dir / "dataset_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        generated_records = int(manifest.get("generated_records", 0))
        manifest.update({
            "version": "4.3.0",
            "source_audit": {
                **source_audit,
                "classifier_ready_unique_records": generated_records,
                "filtered_or_deduplicated_nutrition_records": int(
                    source_audit["nutrition_candidate_input_records"] - generated_records
                ),
            },
        })
        manifest.setdefault("artifacts", {})[source_registry_path.name] = {
            "bytes": source_registry_path.stat().st_size,
            "sha256": sha256(source_registry_path),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest["source_audit"], indent=2))
        return
    foods = build_food_index(args.source_dir)
    safety = build_safety_registry(args.source_dir)
    benchmarks = build_benchmarks(args.source_dir)
    food_path = data_dir / "master_food_index.csv"
    safety_path = data_dir / "food_safety_registry.csv"
    benchmark_path = data_dir / "intake_benchmarks.json"
    foods.to_csv(food_path, index=False)
    safety.to_csv(safety_path, index=False)
    benchmark_path.write_text(json.dumps(benchmarks, indent=2), encoding="utf-8")
    source_registry.to_csv(source_registry_path, index=False)

    portable, metrics = train_portable_model(foods)
    model_path = model_dir / "nutrition_quality_portable.json"
    card_path = model_dir / "nutrition_quality_model_card.json"
    model_path.write_text(json.dumps(portable, separators=(",", ":")), encoding="utf-8")
    card_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    manifest = {
        "version": "4.3.0", "generated_records": int(len(foods)),
        "safety_records": int(len(safety)), "benchmark_records": int(benchmarks["records"]),
        "source_audit": {
            **source_audit,
            "classifier_ready_unique_records": int(len(foods)),
            "filtered_or_deduplicated_nutrition_records": int(
                source_audit["nutrition_candidate_input_records"] - len(foods)
            ),
        },
        "source_files": sorted(path.name for path in args.source_dir.glob("*.csv")),
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in [food_path, safety_path, benchmark_path, source_registry_path, model_path, card_path]
        },
        "model_metrics": metrics,
    }
    (data_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
