from __future__ import annotations

import os
import re
from typing import Any

import requests

from .diet_engine import grocery_list


EMERGENCY_TERMS = ("emergency", "chest pain", "unconscious", "severe breathing", "suicide")
MEDICATION_TERMS = ("medicine", "tablet", "dose", "stop drug", "prescribe", "change medication")
HIGH_RISK_CONDITIONS = {
    "advanced kidney disease", "advanced liver disease", "insulin-treated diabetes",
    "pregnancy", "eating disorder",
}


def assistant_api_status() -> dict[str, Any]:
    url = os.getenv("NUTRIPULSE_ASSISTANT_API_URL", "").strip()
    return {
        "configured": bool(url),
        "mode": "Secure external API adapter" if url else "Advanced grounded assistant",
        "endpoint": url if url else None,
        "capabilities": assistant_capabilities(),
    }


def assistant_capabilities() -> list[str]:
    return [
        "Plan and laboratory explanation",
        "Allergy-aware meal substitutions",
        "Plan-linked grocery lists",
        "Simple recipe and meal-prep guidance",
        "Daily and weekly progress summaries",
        "Clinical safety escalation",
    ]


def _safe_context(
    profile: dict[str, Any], plan: dict[str, Any] | None,
    lab_results: list[dict[str, Any]], progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "goal": profile.get("goal"),
        "activity": profile.get("activity"),
        "cuisine": profile.get("cuisine"),
        "conditions": profile.get("conditions", []),
        "allergies": profile.get("allergies", []),
        "plan": (
            {key: plan.get(key) for key in [
                "title", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g",
                "focus", "status", "days", "linked_lab_summary",
            ]}
            if plan else None
        ),
        "lab_flags": [
            {
                "test": row.get("test"), "value": row.get("value"),
                "unit": row.get("unit"), "flag": row.get("flag"),
            }
            for row in lab_results
        ],
        "progress": progress or {},
        "clinical_boundaries": (
            "Do not diagnose, prescribe, change medicine, or provide emergency care. "
            "High-risk therapeutic plans require qualified professional review."
        ),
    }


def external_answer(
    question: str, profile: dict[str, Any], plan: dict[str, Any] | None,
    lab_results: list[dict[str, Any]], *, progress: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    url = os.getenv("NUTRIPULSE_ASSISTANT_API_URL", "").strip()
    if not url:
        raise ValueError("NUTRIPULSE_ASSISTANT_API_URL is not configured.")
    key = os.getenv("NUTRIPULSE_ASSISTANT_API_KEY", "").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "question": question,
        "context": _safe_context(profile, plan, lab_results, progress),
        "conversation": (conversation_history or [])[-8:],
        "response_contract": {
            "grounded": True,
            "clinical_safety": True,
            "avoid_diagnosis_and_medication_changes": True,
        },
    }
    response = requests.post(url, json=payload, headers=headers, timeout=(4, 20))
    response.raise_for_status()
    body = response.json()
    answer = body.get("answer") or body.get("response") or body.get("message")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Assistant API response must contain answer, response, or message text.")
    return answer.strip()


def _format_lab_summary(labs: list[dict[str, Any]]) -> tuple[str, bool]:
    if not labs:
        return (
            "No verified report is connected yet. Open **Laboratory Intelligence**, upload an image or PDF, "
            "and verify every extracted value before using it for planning.",
            False,
        )
    abnormal = [row for row in labs if str(row.get("flag", "")).lower() in {"high", "low", "critical"}]
    if not abnormal:
        return (
            "The verified values currently stored are within the configured nutrition ranges. "
            "Interpretation still depends on symptoms, diagnosis, medicines and the original laboratory reference ranges.",
            False,
        )
    lines = [
        f"- **{row.get('test', 'Result')}**: {row.get('value', '—')} {row.get('unit', '')} — {str(row.get('flag')).upper()}"
        for row in abnormal[:8]
    ]
    critical = any(str(row.get("flag", "")).lower() == "critical" for row in abnormal)
    ending = (
        "A critical safety gate is present; do not generate or change a therapeutic plan until urgent professional review."
        if critical else
        "These are decision-support flags, not diagnoses. Use the linked plan only as a professional-review draft."
    )
    return "**Verified nutrition-relevant signals**\n\n" + "\n".join(lines) + "\n\n" + ending, True


def _format_plan(plan: dict[str, Any] | None) -> str:
    if not plan:
        return (
            "No active plan is connected. Complete the profile or verify a laboratory report, then open "
            "**Smart Diet Planner** to generate a seven-day review draft."
        )
    focus = ", ".join(str(item) for item in plan.get("focus", [])[:5]) or "balanced food variety"
    status = str(plan.get("status", "review draft")).replace("-", " ")
    return (
        f"**{plan.get('title', 'Active nutrition plan')}**\n\n"
        f"- Energy: **{plan.get('calories', '—')} kcal/day**\n"
        f"- Protein: **{plan.get('protein_g', '—')} g/day**\n"
        f"- Fibre: **{plan.get('fiber_g', '—')} g/day**\n"
        f"- Status: **{status}**\n"
        f"- Main focus: {focus}\n\n"
        "Use portions and substitutions as guidance; allergies and clinician restrictions always take priority."
    )


def _format_grocery_list(plan: dict[str, Any] | None) -> str:
    if not plan:
        return "Generate a plan first so I can build a grocery list from its cuisine and allergy constraints."
    grouped = grocery_list(plan)
    sections = [f"**{group}**\n" + ", ".join(items) for group, items in grouped.items()]
    return (
        "Here is your plan-linked grocery list:\n\n" + "\n\n".join(sections)
        + "\n\nVerify labels and cross-contact controls against every recorded allergy."
    )


def _find_plan_meal(question: str, plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    meals = [meal for day in plan.get("days", []) for meal in day.get("meals", [])]
    if not meals:
        return None
    lowered = question.lower()
    for meal in meals:
        name = str(meal.get("name", "")).lower()
        if name and any(token in lowered for token in re.findall(r"[a-z]{4,}", name)):
            return meal
    meal_slots = {"breakfast": 0, "lunch": 1, "snack": 2, "dinner": 3}
    for slot, index in meal_slots.items():
        if slot in lowered and len(meals) > index:
            return meals[index]
    return meals[0]


def _format_meal_help(question: str, profile: dict[str, Any], plan: dict[str, Any] | None, *, recipe: bool) -> str:
    meal = _find_plan_meal(question, plan)
    if not meal:
        return "Generate a plan first so I can use an actual planned meal, recorded cuisine and allergy constraints."
    name = str(meal.get("name", "Planned meal"))
    detail = str(meal.get("detail", "Use the ingredients shown in your plan."))
    allergies = [str(item) for item in profile.get("allergies", []) if str(item).strip()]
    allergy_note = (
        "Recorded allergies: " + ", ".join(allergies) + ". Verify labels, preparation and cross-contact."
        if allergies else "No allergy is recorded; still verify any ingredient you personally avoid."
    )
    if recipe:
        return (
            f"**Simple plan-linked recipe: {name}**\n\n"
            f"1. Prepare: {detail}.\n"
            "2. Use minimal added salt and measure oils rather than pouring freely.\n"
            "3. Cook the protein and vegetables thoroughly, then serve the planned portion.\n"
            "4. Log any sauces, drinks or portion changes separately.\n\n"
            f"{allergy_note}"
        )
    cuisine = str(profile.get("cuisine", "your selected cuisine"))
    return (
        f"**Suggested plan-safe swap for {name}**\n\n"
        f"Keep the same meal structure—protein, fibre-rich carbohydrate and vegetables—but use another {cuisine} "
        f"combination with a similar portion. Current reference: {detail}.\n\n{allergy_note}"
    )


def _format_progress(progress: dict[str, Any] | None) -> str:
    if not progress:
        return "No schedule progress is available yet. Generate a plan and start clearing meals to build daily and weekly analytics."
    days = progress.get("days", [])
    active_date = progress.get("active_date") or "the current active day"
    active = next((item for item in days if item.get("scheduled_date") == active_date), {})
    completed = int(active.get("completed", 0) or 0)
    total = int(active.get("total", 0) or 0)
    return (
        f"You are on **Week {progress.get('active_week_number', 1)}**, active date **{active_date}**. "
        f"Today has **{completed}/{total} completed meals**. Completed weeks: "
        f"**{progress.get('completed_weeks', 0)}**. Open Progress Analytics for the full trend and skipped-meal history."
    )


def assistant_reply(
    question: str, profile: dict[str, Any], plan: dict[str, Any] | None,
    lab_results: list[dict[str, Any]] | None = None, *, use_external: bool = False,
    progress: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Return grounded guidance plus transparent intent and safety metadata."""
    text = question.lower().strip()
    labs = lab_results or []
    conditions = {str(item).strip().lower() for item in profile.get("conditions", []) if str(item).strip()}
    clinical_review = bool(conditions & HIGH_RISK_CONDITIONS)
    intent = "general_nutrition"
    confidence = "Moderate"
    grounding = ["Customer profile"]
    suggested_actions = ["Ask a follow-up question", "Review the active plan"]

    if any(term in text for term in EMERGENCY_TERMS):
        return {
            "answer": (
                "This may be urgent. NutriPulse cannot provide emergency care. Contact your local emergency "
                "service or go to the nearest emergency department now."
            ),
            "intent": "emergency_escalation", "confidence": "Safety rule",
            "grounding": ["Emergency safety policy"], "clinical_review_required": True,
            "suggested_actions": ["Contact local emergency services now"],
        }
    if any(term in text for term in MEDICATION_TERMS):
        return {
            "answer": (
                "I cannot start, stop or change medicines or therapeutic supplement doses. "
                "Please discuss this with the prescribing clinician or pharmacist."
            ),
            "intent": "medication_boundary", "confidence": "Safety rule",
            "grounding": ["Medication safety policy"], "clinical_review_required": True,
            "suggested_actions": ["Message the assigned care team"],
        }

    if use_external:
        try:
            answer = external_answer(
                question, profile, plan, labs, progress=progress,
                conversation_history=conversation_history,
            )
            return {
                "answer": answer, "intent": "external_grounded_response", "confidence": "External adapter",
                "grounding": ["Consent-approved profile context", "Configured assistant API"],
                "clinical_review_required": clinical_review,
                "suggested_actions": suggested_actions,
            }
        except (requests.RequestException, ValueError, TypeError) as exc:
            fallback = assistant_reply(
                question, profile, plan, labs, use_external=False, progress=progress,
                conversation_history=conversation_history,
            )
            fallback["answer"] = f"The configured assistant API is unavailable ({exc}).\n\n" + str(fallback["answer"])
            return fallback

    if any(term in text for term in ("what can you do", "help me", "capabilities", "features")):
        intent, confidence = "capabilities", "High"
        answer = "I can help with:\n\n" + "\n".join(f"- {item}" for item in assistant_capabilities())
        grounding = ["NutriGuide capability registry"]
    elif "grocery" in text or "shopping list" in text:
        intent, confidence = "grocery_list", "High"
        answer = _format_grocery_list(plan)
        grounding = ["Active diet plan", "Cuisine and allergy constraints"]
    elif any(term in text for term in ("recipe", "how to cook", "meal prep", "prepare this")):
        intent, confidence = "recipe", "Moderate"
        answer = _format_meal_help(question, profile, plan, recipe=True)
        grounding = ["Active plan meal", "Customer allergies", "Customer cuisine"]
    elif any(term in text for term in ("swap", "substitute", "replace", "alternative meal")):
        intent, confidence = "meal_substitution", "Moderate"
        answer = _format_meal_help(question, profile, plan, recipe=False)
        grounding = ["Active plan meal", "Customer allergies", "Customer cuisine"]
    elif any(term in text for term in ("progress", "adherence", "completed week", "how am i doing")):
        intent, confidence = "progress_summary", "High"
        answer = _format_progress(progress)
        grounding = ["Persisted meal schedule progress"]
    elif "lab" in text or "report" in text or "result" in text:
        intent, confidence = "laboratory_explanation", "High"
        answer, flagged = _format_lab_summary(labs)
        clinical_review = clinical_review or flagged
        grounding = ["Latest verified laboratory report", "Configured clinical safety rules"]
        suggested_actions = ["Review Laboratory Intelligence", "Ask the assigned Dietitian"]
    elif "protein" in text:
        intent, confidence = "protein_target", "High" if plan else "Moderate"
        target = plan.get("protein_g") if plan else "your calculated"
        answer = (
            f"Your connected daily protein target is **{target} g**. Suitable choices may include pulses, eggs, "
            "unsweetened yogurt, fish, chicken, tofu or paneer, adjusted for recorded allergies and kidney status."
        )
        grounding = ["Active diet plan" if plan else "Customer profile"]
    elif any(term in text for term in ("sugar", "a1c", "diabetes", "glucose")):
        intent = "glucose_nutrition"
        answer = (
            "Distribute carbohydrate across meals, prefer minimally processed high-fibre choices, and pair them "
            "with protein. Insulin-treated diabetes or severe glucose results require professional review."
        )
        clinical_review = clinical_review or "insulin-treated diabetes" in conditions
        grounding = ["Customer conditions", "Verified laboratory flags"]
    elif any(term in text for term in ("kidney", "creatinine", "egfr", "potassium")):
        intent, clinical_review = "renal_safety", True
        answer = (
            "Kidney diets cannot be safely generated from one result. eGFR, potassium, medicines, fluid status "
            "and the full diagnosis must be reviewed by a qualified clinician."
        )
        grounding = ["Renal clinical safety rule", "Verified laboratory flags"]
    elif "plan" in text or "diet" in text:
        intent, confidence = "plan_explanation", "High" if plan else "Moderate"
        answer = _format_plan(plan)
        grounding = ["Active diet plan", "Plan-linked laboratory strategy"] if plan else ["Customer profile"]
    elif "weight" in text or "calorie" in text or "energy" in text:
        intent, confidence = "energy_target", "High"
        answer = (
            f"Your current goal is **{profile.get('goal', 'wellness')}**. Energy targets use age, biological sex, "
            "height, weight and activity, followed by a conservative goal adjustment."
        )
        grounding = ["Customer profile", "NutriPulse energy calculation"]
    else:
        answer = (
            "I can explain nutrition targets and laboratory-linked plan logic, build a grocery list, suggest "
            "allergy-aware meal swaps, create simple plan-linked recipes, and summarize weekly progress. "
            "I do not diagnose conditions or prescribe treatment."
        )

    return {
        "answer": answer,
        "intent": intent,
        "confidence": confidence,
        "grounding": grounding,
        "clinical_review_required": clinical_review,
        "suggested_actions": suggested_actions,
    }


def answer_question(
    question: str, profile: dict[str, Any], plan: dict[str, Any] | None,
    lab_results: list[dict[str, Any]] | None = None, *, use_external: bool = False,
    progress: dict[str, Any] | None = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Compatibility wrapper used by the API and existing integrations."""
    return str(assistant_reply(
        question, profile, plan, lab_results, use_external=use_external,
        progress=progress, conversation_history=conversation_history,
    )["answer"])
