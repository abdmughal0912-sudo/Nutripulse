from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from .clinical_planner import apply_lab_strategy, build_lab_strategy, strategy_macros
from .lab_analyzer import assess_safety
from .nutrition import calculate_energy, macro_targets

PAKISTANI_DAYS = [
    [
        ("08:00", "Oat and yogurt fruit bowl", "Oats, unsweetened yogurt, berries or guava, chia", 410, 25),
        ("12:45", "Chicken chickpea salad bowl", "Grilled chicken, chickpeas, cucumber, tomato, lemon", 560, 43),
        ("16:30", "Apple and almond butter", "One apple with unsalted almond butter", 210, 6),
        ("20:00", "Masoor daal with vegetables", "Masoor daal, mixed vegetables, small whole-wheat roti", 560, 31),
    ],
    [
        ("08:00", "Egg and spinach roti wrap", "Eggs, spinach, tomato and whole-wheat roti", 430, 27),
        ("13:00", "Daal, brown rice and raita", "Daal, controlled brown-rice portion and cucumber raita", 570, 27),
        ("16:30", "Guava and walnuts", "Fresh guava with unsalted walnuts", 190, 5),
        ("20:00", "Herb chicken vegetable plate", "Grilled chicken, seasonal vegetables and barley", 570, 47),
    ],
    [
        ("08:00", "Besan vegetable chilla", "Gram flour, vegetables and mint yogurt", 405, 22),
        ("12:45", "Tuna bean garden salad", "Tuna, white beans, leaves, olive oil and lemon", 550, 41),
        ("16:30", "Yogurt with flax", "Unsweetened yogurt, ground flax and cinnamon", 190, 13),
        ("20:00", "Lean beef and vegetable stew", "Lean beef, beans, tomato and vegetables", 600, 44),
    ],
    [
        ("08:00", "Vegetable omelette and toast", "Egg, peppers, onion and whole-grain toast", 420, 26),
        ("12:45", "Chana chaat power bowl", "Chickpeas, cucumber, tomato, herbs and yogurt", 540, 25),
        ("16:30", "Pear and pumpkin seeds", "Fresh pear with unsalted pumpkin seeds", 210, 7),
        ("20:00", "Baked fish with lentils", "Fish, lentils, broccoli and lemon", 590, 45),
    ],
    [
        ("08:00", "Cinnamon overnight oats", "Oats, milk or fortified alternative, chia and fruit", 415, 21),
        ("12:45", "Chicken daal combination plate", "Lean chicken, moong daal, salad and small roti", 590, 46),
        ("16:30", "Carrot sticks and hummus", "Carrot and cucumber with hummus", 180, 6),
        ("20:00", "Vegetable barley khichdi", "Barley, lentils, vegetables and yogurt", 565, 28),
    ],
    [
        ("08:30", "Yogurt parfait with nuts", "Unsweetened yogurt, seasonal fruit, oats and nuts", 420, 24),
        ("13:15", "Grilled fish grain bowl", "Fish, brown rice, greens and yogurt dressing", 580, 42),
        ("17:00", "Orange and roasted chana", "Orange with unsalted roasted chickpeas", 205, 8),
        ("20:15", "Chicken vegetable karahi", "Low-oil chicken karahi, vegetables and small roti", 570, 44),
    ],
    [
        ("08:30", "Paneer or tofu scramble", "Low-fat paneer or tofu, vegetables and whole-grain toast", 430, 27),
        ("13:15", "Rajma salad plate", "Kidney beans, salad, yogurt and small brown-rice portion", 565, 28),
        ("17:00", "Fruit and seed bowl", "Seasonal fruit with chia and pumpkin seeds", 195, 6),
        ("20:00", "Lentil soup and grilled chicken", "Lentil vegetable soup with lean grilled chicken", 595, 48),
    ],
]

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _substitute(text: str, replacements: list[tuple[str, str]]) -> str:
    """Apply readable, case-insensitive ingredient substitutions."""
    result = text
    for source, target in replacements:
        result = re.sub(rf"\b{re.escape(source)}\b", target, result, flags=re.IGNORECASE)
    return result


def apply_dietary_constraints(name: str, detail: str, profile: dict[str, Any]) -> tuple[str, str]:
    """Apply the supported cuisine and allergy constraints to a meal description.

    This is deliberately deterministic and visible to the user. It does not claim that
    a text substitution eliminates kitchen cross-contact risk.
    """
    allergies = {str(item).lower() for item in profile.get("allergies", [])}
    cuisine = str(profile.get("cuisine", "")).lower()
    vegan = cuisine == "vegan"
    vegetarian = vegan or cuisine == "vegetarian"
    soy_safe = "soy" not in allergies

    replacements: list[tuple[str, str]] = []
    if vegetarian:
        plant_protein = "tofu" if soy_safe else "chickpea patties"
        replacements.extend([
            ("lean grilled chicken", plant_protein), ("grilled chicken", plant_protein),
            ("chicken breast", plant_protein), ("lean chicken", plant_protein),
            ("chicken", plant_protein), ("lean beef", plant_protein),
            ("beef", plant_protein), ("tuna", plant_protein), ("fish", plant_protein),
        ])
    if vegan:
        egg_swap = "tofu scramble" if soy_safe else "chickpea scramble"
        dairy_swap = "unsweetened soy cultured alternative" if soy_safe else "unsweetened oat cultured alternative"
        replacements.extend([
            ("vegetable omelette", "vegetable " + egg_swap),
            ("eggs", egg_swap), ("egg", egg_swap),
            ("low-fat paneer", "tofu" if soy_safe else "chickpea curd"),
            ("paneer", "tofu" if soy_safe else "chickpea curd"),
            ("cucumber raita", "cucumber " + dairy_swap),
            ("mint yogurt", "mint " + dairy_swap),
            ("unsweetened yogurt", dairy_swap),
            ("yogurt", dairy_swap),
            ("milk", "fortified soy drink" if soy_safe else "fortified oat drink"),
        ])
    if "egg" in allergies:
        replacements.extend([
            ("vegetable omelette", "vegetable chickpea scramble"),
            ("eggs", "chickpea scramble"), ("egg", "chickpea scramble"),
        ])
    if "fish" in allergies or "shellfish" in allergies:
        protein_swap = "tofu" if vegetarian and soy_safe else "chickpea patties" if vegetarian else "grilled chicken"
        replacements.extend([("tuna", protein_swap), ("fish", protein_swap)])
    if "milk" in allergies or "lactose" in allergies:
        dairy_swap = "unsweetened soy cultured alternative" if soy_safe else "unsweetened oat cultured alternative"
        replacements.extend([
            ("low-fat paneer", "tofu" if soy_safe else "chickpea curd"),
            ("paneer", "tofu" if soy_safe else "chickpea curd"),
            ("cucumber raita", "cucumber " + dairy_swap),
            ("mint yogurt", "mint " + dairy_swap),
            ("unsweetened yogurt", dairy_swap),
            ("yogurt", dairy_swap),
            ("milk", "fortified soy drink" if soy_safe else "fortified oat drink"),
        ])
    if "tree nuts" in allergies:
        replacements.extend([
            ("almond butter", "sunflower-seed butter"),
            ("walnuts", "pumpkin seeds"), ("nuts", "seeds"),
        ])
    if "peanuts" in allergies:
        replacements.extend([("peanut butter", "sunflower-seed butter"), ("peanuts", "pumpkin seeds")])
    if "wheat/gluten" in allergies:
        replacements.extend([
            ("whole-wheat roti", "certified gluten-free millet roti"),
            ("whole-grain toast", "certified gluten-free toast"),
            ("small roti", "small certified gluten-free millet roti"),
            ("barley", "quinoa"), ("atta", "gluten-free millet flour"),
        ])
    if "soy" in allergies:
        replacements.extend([
            ("unsweetened soy cultured alternative", "unsweetened oat cultured alternative"),
            ("fortified soy drink", "fortified oat drink"),
            ("tofu scramble", "chickpea scramble"), ("tofu", "chickpea patties"),
            ("soy", "chickpea-based"),
        ])

    unique_replacements: dict[str, str] = {}
    for source, target in replacements:
        unique_replacements[source] = target
    converted_name = _substitute(name, list(unique_replacements.items()))
    converted_detail = _substitute(detail, list(unique_replacements.items()))
    for repeated, clean in [
        ("tofu or tofu", "tofu"),
        ("chickpea patties or chickpea patties", "chickpea patties"),
        ("unsweetened oat cultured alternative unsweetened oat cultured alternative", "unsweetened oat cultured alternative"),
        ("unsweetened soy cultured alternative unsweetened soy cultured alternative", "unsweetened soy cultured alternative"),
    ]:
        converted_name = converted_name.replace(repeated, clean)
        converted_detail = converted_detail.replace(repeated, clean)
    return converted_name, converted_detail


def nutrition_focus(labs: list[dict[str, Any]], profile: dict[str, Any]) -> list[str]:
    focus = ["Food variety", "Adequate fibre", "Minimally processed foods", "Hydration"]
    names = {row["test"]: row for row in labs}
    if names.get("HbA1c", {}).get("flag") in {"high", "critical"} or float(names.get("HbA1c", {}).get("value", 0)) >= 5.7:
        focus.extend(["Steady carbohydrate distribution", "Low added sugar"])
    if names.get("LDL cholesterol", {}).get("flag") == "high":
        focus.extend(["Soluble fibre", "Unsaturated fats"])
    if names.get("Vitamin D", {}).get("flag") == "low":
        focus.append("Vitamin D food sources")
    if names.get("Haemoglobin", {}).get("flag") == "low":
        focus.append("Cause-specific anaemia review")
    if "Hypertension" in profile.get("conditions", []):
        focus.append("Lower-sodium food pattern")
    allergies = profile.get("allergies", [])
    if allergies:
        focus.append("Avoid declared allergens: " + ", ".join(map(str, allergies)))
    if profile.get("cuisine") in {"Vegetarian", "Vegan"}:
        focus.append(f"{profile['cuisine']} protein variety")
    return list(dict.fromkeys(focus))


def generate_plan(profile: dict[str, Any], labs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    labs = labs or []
    safety = assess_safety(labs, profile)
    if not safety["can_generate"]:
        raise ValueError("Plan generation blocked: " + "; ".join(safety["reasons"]))
    energy = calculate_energy(profile)
    strategy = build_lab_strategy(labs, profile)
    macros = strategy_macros(energy["target_calories"], profile, strategy)
    template_average = sum(meal[3] for meal in PAKISTANI_DAYS[0])
    scale = energy["target_calories"] / template_average
    days = []
    for day_name, day_template in zip(DAY_NAMES, PAKISTANI_DAYS):
        meals = []
        for time, name, detail, calories, protein in day_template:
            lab_name, lab_detail = apply_lab_strategy(name, detail, time, strategy)
            constrained_name, constrained_detail = apply_dietary_constraints(lab_name, lab_detail, profile)
            meals.append({
                "time": time,
                "name": constrained_name,
                "detail": constrained_detail,
                "calories": round(calories * scale),
                "protein_g": round(protein * scale),
                "clinical_tags": strategy["tags"],
            })
        days.append({"day": day_name, "meals": meals})
    return {
        "title": strategy["title"],
        "calories": energy["target_calories"],
        "bmr": energy["bmr"],
        "tdee": energy["tdee"],
        "protein_g": macros["protein_g"],
        "carbs_g": macros["carbs_g"],
        "fat_g": macros["fat_g"],
        "fiber_g": macros["fiber_g"],
        "water_l": macros["water_l"],
        "focus": nutrition_focus(labs, profile),
        "plan_adjustments": strategy["adjustments"],
        "strategy_tags": strategy["tags"],
        "linked_lab_summary": strategy["linked_labs"],
        "lab_signature": strategy["lab_signature"],
        "requires_macro_review": strategy["requires_macro_review"],
        "status": safety["level"],
        "safety_reasons": safety["reasons"],
        "dietary_constraints": list(profile.get("allergies", [])),
        "cuisine": profile.get("cuisine", "Pakistani + international"),
        "cross_contact_notice": "Ingredient substitutions do not guarantee an allergen-free kitchen; verify labels and cross-contact controls.",
        "days": days,
        "profile_snapshot": deepcopy(profile),
    }


def grocery_list(plan: dict[str, Any]) -> dict[str, list[str]]:
    groceries = {
        "Produce": ["Seasonal fruit", "Spinach", "Cucumber", "Tomato", "Broccoli", "Carrots", "Lemon", "Fresh herbs"],
        "Proteins": ["Chicken breast", "Fish", "Eggs", "Tuna", "Lean beef", "Low-fat paneer or tofu"],
        "Pulses & grains": ["Masoor daal", "Moong daal", "Chickpeas", "Kidney beans", "Oats", "Brown rice", "Barley", "Whole-wheat atta"],
        "Healthy fats": ["Unsalted walnuts", "Almond butter", "Chia", "Flax", "Pumpkin seeds", "Olive oil"],
        "Dairy / alternatives": ["Unsweetened yogurt", "Milk or fortified unsweetened alternative"],
    }
    profile = plan.get("profile_snapshot", {})
    constrained: dict[str, list[str]] = {}
    for group, items in groceries.items():
        converted = [apply_dietary_constraints(item, item, profile)[0] for item in items]
        constrained[group] = list(dict.fromkeys(converted))
    return constrained


def plan_day_totals(day: dict[str, Any]) -> dict[str, int]:
    return {
        "calories": sum(int(meal["calories"]) for meal in day["meals"]),
        "protein_g": sum(int(meal["protein_g"]) for meal in day["meals"]),
    }
