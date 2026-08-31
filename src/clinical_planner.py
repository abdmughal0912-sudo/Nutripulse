from __future__ import annotations

import hashlib
import re
from typing import Any

from .nutrition import macro_targets


def _substitute(text: str, replacements: list[tuple[str, str]]) -> str:
    result = text
    for source, target in replacements:
        result = re.sub(rf"\b{re.escape(source)}\b", target, result, flags=re.IGNORECASE)
    return result


def _lab_map(labs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for source in labs:
        test = str(source.get("test", "")).strip()
        if not test:
            continue
        try:
            value = float(source.get("value"))
        except (TypeError, ValueError):
            continue
        normalized[test.lower()] = {
            "test": test,
            "value": value,
            "unit": str(source.get("unit", "")).strip(),
            "reference": str(source.get("reference", "")).strip(),
            "flag": str(source.get("flag", "unverified")).lower(),
        }
    return normalized


def build_lab_strategy(labs: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    """Convert verified findings into transparent nutrition-planning constraints.

    This is decision support, not diagnosis. Kidney, electrolyte, thyroid, supplement
    and other therapeutic decisions remain clinician-led.
    """
    rows = _lab_map(labs)
    conditions = {
        str(item).strip().lower()
        for item in profile.get("conditions", [])
        if str(item).strip()
    }
    condition_text = " ".join(sorted(conditions))
    tags: list[str] = []
    adjustments: list[str] = []
    responses: dict[str, str] = {}

    def add(tag: str, adjustment: str) -> None:
        if tag not in tags:
            tags.append(tag)
        if adjustment not in adjustments:
            adjustments.append(adjustment)

    def flagged(names: set[str], flags: set[str]) -> list[dict[str, Any]]:
        return [
            row for name, row in rows.items()
            if name in names and row["flag"] in flags
        ]

    glucose_tests = {"hba1c", "fasting glucose", "random glucose"}
    lipid_tests = {
        "ldl cholesterol", "hdl cholesterol",
        "triglycerides", "total cholesterol",
    }
    kidney_tests = {"egfr", "creatinine", "urea", "bun"}
    electrolyte_tests = {
        "potassium", "sodium", "calcium", "magnesium", "phosphate",
    }
    liver_tests = {"alt", "ast", "alp", "total bilirubin", "albumin"}
    blood_tests = {
        "haemoglobin", "ferritin", "haematocrit", "mcv", "mch", "mchc",
    }

    glucose_rows = flagged(glucose_tests, {"high", "critical"})
    glucose_condition = any(
        term in condition_text
        for term in ("diabetes", "prediabetes", "insulin resistance")
    )
    if glucose_rows or glucose_condition:
        add(
            "glucose-aware",
            "Distribute measured high-fibre carbohydrate portions across the day "
            "and avoid concentrated added sugar.",
        )
        for row in glucose_rows:
            responses[row["test"].lower()] = (
                "Lower-glycaemic meal structure and steadier carbohydrate distribution."
            )

    lipid_rows = flagged(
        {"ldl cholesterol", "triglycerides", "total cholesterol"},
        {"high", "critical"},
    )
    lipid_rows.extend(flagged({"hdl cholesterol"}, {"low", "critical"}))
    lipid_present = any(name in rows for name in lipid_tests)
    if lipid_rows:
        add(
            "lipid-aware",
            "Increase soluble fibre and unsaturated-fat foods while replacing "
            "frequent red-meat and saturated-fat choices.",
        )
        for row in lipid_rows:
            responses[row["test"].lower()] = (
                "Soluble fibre, legumes and unsaturated-fat substitutions."
            )
    elif lipid_present:
        add(
            "lipid-maintenance",
            "Maintain a cardioprotective pattern because the verified lipid values "
            "do not justify an unnecessary therapeutic restriction.",
        )
        for name in lipid_tests & rows.keys():
            responses[name] = (
                "Maintain soluble fibre, legumes and suitable unsaturated fats."
            )

    low_vitamin_d = flagged({"vitamin d"}, {"low"})
    if low_vitamin_d:
        add(
            "vitamin-d-food-support",
            "Include vitamin-D-fortified foods and suitable egg, fish or mushroom "
            "choices; supplement dosing remains clinician-led.",
        )
        responses["vitamin d"] = (
            "Food-first vitamin D sources; no autonomous supplement dose."
        )

    low_b_vitamins = flagged({"vitamin b12", "folate"}, {"low"})
    if low_b_vitamins:
        add(
            "b-vitamin-food-support",
            "Use suitable B12/folate foods or fortified alternatives while retaining "
            "professional cause and supplement review.",
        )
        for row in low_b_vitamins:
            responses[row["test"].lower()] = (
                "Food or fortified-source support with professional cause review."
            )

    blood_rows = flagged(blood_tests, {"low"})
    if blood_rows:
        add(
            "blood-building-food-support",
            "Pair iron-containing foods with vitamin-C-rich produce; low blood counts "
            "still require cause-specific clinical review.",
        )
        for row in blood_rows:
            responses[row["test"].lower()] = (
                "Iron/folate/B12 food pairing without assuming the cause."
            )

    inflammation_rows = flagged({"crp"}, {"high", "critical"})
    if inflammation_rows:
        add(
            "anti-inflammatory-pattern",
            "Prioritize colourful vegetables, pulses, whole grains and unsaturated "
            "fats; CRP is not treated as a nutrition diagnosis.",
        )
        responses["crp"] = (
            "Whole-food anti-inflammatory pattern with medical interpretation retained."
        )

    liver_rows = flagged(liver_tests, {"high", "low", "critical"})
    if liver_rows or "fatty liver" in condition_text:
        add(
            "liver-review-pattern",
            "Use minimally processed, lower-added-sugar meals without making "
            "therapeutic liver claims before professional review.",
        )
        for row in liver_rows:
            responses[row["test"].lower()] = (
                "Minimally processed pattern; liver abnormality requires clinical interpretation."
            )

    urate_rows = flagged({"uric acid"}, {"high", "critical"})
    if urate_rows or "gout" in condition_text:
        add(
            "urate-aware",
            "Emphasize hydration and replace frequent red-meat or organ-meat choices; "
            "medicines and kidney function still matter.",
        )
        if urate_rows:
            responses["uric acid"] = (
                "Hydration and lower-purine substitutions with clinical review."
            )

    if "hypertension" in condition_text or "high blood pressure" in condition_text:
        add(
            "lower-sodium-pattern",
            "Prepare meals without stock cubes and with measured salt, using herbs, "
            "lemon and spices for flavour.",
        )

    kidney_rows = flagged(kidney_tests, {"high", "low", "critical"})
    electrolyte_rows = flagged(
        electrolyte_tests, {"high", "low", "critical"}
    )
    if kidney_rows:
        add(
            "kidney-clinician-review",
            "Keep protein and renal restrictions provisional: kidney findings require "
            "eGFR, medicines, hydration and diagnosis review.",
        )
        for row in kidney_rows:
            responses[row["test"].lower()] = (
                "No autonomous renal restriction; qualified clinician review required."
            )
    if electrolyte_rows:
        add(
            "electrolyte-clinician-review",
            "Do not self-correct serum electrolytes with food restriction or "
            "supplementation; retain clinician review.",
        )
        for row in electrolyte_rows:
            responses[row["test"].lower()] = (
                "No autonomous electrolyte restriction or supplementation."
            )

    thyroid_rows = flagged({"tsh", "free t4"}, {"high", "low", "critical"})
    if thyroid_rows:
        add(
            "thyroid-clinician-review",
            "Do not substitute diet changes for thyroid assessment or prescribed treatment.",
        )
        for row in thyroid_rows:
            responses[row["test"].lower()] = (
                "Professional thyroid interpretation; no therapeutic food claim."
            )

    if not tags and rows:
        add(
            "lab-informed-maintenance",
            "Keep a varied wellness pattern; verified normal findings do not justify "
            "unnecessary food restriction.",
        )

    for name, row in rows.items():
        if name in responses:
            continue
        responses[name] = (
            "Verified normal value monitored without unnecessary restriction."
            if row["flag"] == "normal"
            else "No automated therapeutic change; retain professional review."
        )

    title_by_tag = {
        "glucose-aware": "Glucose-aware fibre and meal-timing plan",
        "lipid-aware": "Lipid-aware soluble-fibre and unsaturated-fat plan",
        "blood-building-food-support": "Blood-count-aware food-support plan",
        "vitamin-d-food-support": "Vitamin-D food-support plan",
        "b-vitamin-food-support": "B-vitamin food-support plan",
        "liver-review-pattern": "Liver-review whole-food plan",
        "urate-aware": "Urate-aware hydration and protein-selection plan",
        "anti-inflammatory-pattern": "Inflammation-aware whole-food plan",
        "lower-sodium-pattern": "Lower-sodium cardiometabolic plan",
        "lipid-maintenance": "Lipid-maintenance cardiometabolic plan",
        "lab-informed-maintenance": "Verified-lab wellness maintenance plan",
    }
    title = next(
        (title_by_tag[tag] for tag in tags if tag in title_by_tag),
        "Personalized cardiometabolic balance plan",
    )
    linked_labs = [
        {
            "test": row["test"],
            "value": row["value"],
            "unit": row["unit"],
            "reference": row["reference"],
            "flag": row["flag"],
            "plan_response": responses[name],
        }
        for name, row in rows.items()
    ]
    signature_source = "|".join(
        f"{row['test']}:{row['value']}:{row['unit']}:{row['flag']}"
        for row in linked_labs
    )
    review_tags = {"kidney-clinician-review", "electrolyte-clinician-review"}
    return {
        "title": title,
        "tags": tags,
        "adjustments": adjustments,
        "linked_labs": linked_labs,
        "lab_signature": (
            hashlib.sha256(signature_source.encode("utf-8")).hexdigest()[:12]
            if signature_source else "wellness-only"
        ),
        "requires_macro_review": bool(review_tags & set(tags)),
    }


def strategy_macros(
    calories: float,
    profile: dict[str, Any],
    strategy: dict[str, Any],
) -> dict[str, float]:
    tags = set(strategy["tags"])
    high_protein = profile.get("goal") in {"Fat loss", "Performance"}
    if "kidney-clinician-review" in tags:
        high_protein = False
    macros = macro_targets(calories, high_protein=high_protein)
    if "glucose-aware" in tags:
        protein_pct = 0.25 if "kidney-clinician-review" in tags else (
            0.30 if high_protein else 0.27
        )
        carb_pct = 0.40 if "kidney-clinician-review" in tags else 0.39
        fat_pct = 1 - protein_pct - carb_pct
        macros.update({
            "protein_g": round(calories * protein_pct / 4),
            "carbs_g": round(calories * carb_pct / 4),
            "fat_g": round(calories * fat_pct / 9),
            "fiber_g": 38,
        })
    if {"lipid-aware", "lipid-maintenance"} & tags:
        macros["fiber_g"] = max(float(macros["fiber_g"]), 38)
    return macros


def apply_lab_strategy(
    name: str,
    detail: str,
    meal_time: str,
    strategy: dict[str, Any],
) -> tuple[str, str]:
    """Change actual meals, not only headings, from the verified strategy."""
    tags = set(strategy["tags"])
    replacements: list[tuple[str, str]] = []
    if "glucose-aware" in tags:
        replacements.extend([
            ("Oat and yogurt fruit bowl", "Measured oat, yogurt and berry bowl"),
            (
                "Oats, unsweetened yogurt, berries or guava, chia",
                "Measured oats, unsweetened yogurt, berries or guava, chia and cinnamon",
            ),
            ("Daal, brown rice and raita", "Daal, barley and raita plate"),
            ("controlled brown-rice portion", "measured barley or quinoa portion"),
            ("Fruit and seed bowl", "Guava and seed bowl"),
            ("seasonal fruit", "guava, pear or berries"),
        ])
    if {"lipid-aware", "lipid-maintenance"} & tags:
        replacements.extend([
            ("Lean beef and vegetable stew", "Bean, barley and vegetable stew"),
            (
                "Lean beef, beans, tomato and vegetables",
                "Mixed beans, barley, tomato and vegetables",
            ),
            ("Paneer or tofu scramble", "Tofu and vegetable scramble"),
            ("Low-fat paneer or tofu", "tofu and chickpeas"),
            ("Apple and almond butter", "Apple and unsalted seed butter"),
        ])
    if "vitamin-d-food-support" in tags:
        replacements.extend([
            ("Cinnamon overnight oats", "Vitamin-D-fortified overnight oats"),
            (
                "milk or fortified alternative",
                "vitamin-D-fortified milk or alternative",
            ),
            ("Baked fish with lentils", "Baked fish with mushroom-lentil medley"),
            (
                "Fish, lentils, broccoli and lemon",
                "Fish, UV-exposed mushrooms, lentils, broccoli and lemon",
            ),
        ])
    if "blood-building-food-support" in tags:
        replacements.extend([
            ("Egg and spinach roti wrap", "Spinach, egg and lemon roti wrap"),
            (
                "Eggs, spinach, tomato and whole-wheat roti",
                "Eggs, spinach, tomato, lemon and whole-wheat roti",
            ),
            ("Masoor daal with vegetables", "Masoor daal with spinach and lemon"),
            (
                "Masoor daal, mixed vegetables, small whole-wheat roti",
                "Masoor daal, spinach, peppers, lemon and small whole-wheat roti",
            ),
        ])
    if "b-vitamin-food-support" in tags:
        replacements.extend([
            ("Yogurt with flax", "B12-fortified yogurt with flax"),
            (
                "Unsweetened yogurt, ground flax and cinnamon",
                "B12-fortified unsweetened yogurt, ground flax and cinnamon",
            ),
            (
                "Chana chaat power bowl",
                "Chana, leafy-green and fortified-yogurt bowl",
            ),
        ])
    if "liver-review-pattern" in tags:
        replacements.extend([
            ("Chicken vegetable karahi", "Low-oil herb chicken vegetable karahi"),
            ("Low-oil chicken karahi", "low-oil herb chicken karahi"),
            ("Lean beef and vegetable stew", "Herb chicken and vegetable stew"),
        ])
    if "urate-aware" in tags:
        replacements.extend([
            ("Tuna bean garden salad", "Egg and garden bean salad"),
            ("Tuna, white beans", "Egg, white beans"),
            ("Lean beef and vegetable stew", "Chicken and vegetable stew"),
            ("Lean beef, beans", "Chicken, beans"),
        ])

    converted_name = _substitute(name, replacements)
    converted_detail = _substitute(detail, replacements)
    preparation_notes: list[str] = []
    if "lower-sodium-pattern" in tags and meal_time >= "12:00":
        preparation_notes.append(
            "prepared without stock cubes and with measured salt"
        )
    if "anti-inflammatory-pattern" in tags and meal_time >= "12:00":
        preparation_notes.append(
            "include colourful vegetables, herbs and suitable unsaturated oil"
        )
    if preparation_notes:
        converted_detail = (
            converted_detail.rstrip(". ")
            + "; "
            + "; ".join(preparation_notes)
        )
    return converted_name, converted_detail
