from __future__ import annotations

import os
from typing import Any

import requests


def assistant_api_status() -> dict[str, Any]:
    url = os.getenv("NUTRIPULSE_ASSISTANT_API_URL", "").strip()
    return {
        "configured": bool(url),
        "mode": "Secure external API adapter" if url else "Built-in grounded assistant",
        "endpoint": url if url else None,
    }


def external_answer(question: str, profile: dict[str, Any], plan: dict[str, Any] | None,
                    lab_results: list[dict[str, Any]]) -> str:
    url = os.getenv("NUTRIPULSE_ASSISTANT_API_URL", "").strip()
    if not url:
        raise ValueError("NUTRIPULSE_ASSISTANT_API_URL is not configured.")
    key = os.getenv("NUTRIPULSE_ASSISTANT_API_KEY", "").strip()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    safe_context = {
        "goal": profile.get("goal"), "activity": profile.get("activity"),
        "conditions": profile.get("conditions", []), "allergies": profile.get("allergies", []),
        "plan": ({key: plan.get(key) for key in ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "focus", "status"]} if plan else None),
        "lab_flags": [
            {"test": row.get("test"), "value": row.get("value"), "unit": row.get("unit"), "flag": row.get("flag")}
            for row in lab_results
        ],
        "clinical_boundaries": "Do not diagnose, prescribe, change medicine, or provide emergency care.",
    }
    response = requests.post(url, json={"question": question, "context": safe_context}, headers=headers, timeout=(4, 20))
    response.raise_for_status()
    payload = response.json()
    answer = payload.get("answer") or payload.get("response") or payload.get("message")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Assistant API response must contain answer, response, or message text.")
    return answer.strip()


def answer_question(question: str, profile: dict[str, Any], plan: dict[str, Any] | None,
                    lab_results: list[dict[str, Any]] | None = None, *,
                    use_external: bool = False) -> str:
    text = question.lower().strip()
    labs = lab_results or []
    if any(term in text for term in ["emergency", "chest pain", "unconscious", "severe breathing", "suicide"]):
        return (
            "This may be urgent. NutriPulse cannot provide emergency care. Contact your local emergency "
            "service or go to the nearest emergency department now."
        )
    if any(term in text for term in ["medicine", "tablet", "dose", "stop drug", "prescribe"]):
        return (
            "I cannot start, stop or change medicines or therapeutic supplement doses. "
            "Please discuss this with the prescribing clinician."
        )
    if use_external:
        try:
            return external_answer(question, profile, plan, labs)
        except (requests.RequestException, ValueError, TypeError) as exc:
            return f"The configured assistant API is unavailable ({exc}). Built-in safe guidance: " + answer_question(
                question, profile, plan, labs, use_external=False,
            )
    if "lab" in text or "report" in text:
        if not labs:
            return (
                "Open Laboratory Intelligence, upload an image or PDF, and verify every extracted value. "
                "The safety engine will either prepare a review-ready nutrition draft or block high-risk results."
            )
        abnormal = [row for row in labs if row.get("flag") in {"high", "low", "critical"}]
        if not abnormal:
            return "The verified values currently stored are within the configured ranges. Interpretation still depends on clinical context."
        summary = ", ".join(f"{row['test']} ({row['flag']})" for row in abnormal)
        return f"The verified nutrition-relevant signals are: {summary}. These are decision-support flags, not diagnoses."
    if "protein" in text:
        target = plan.get("protein_g") if plan else "your calculated"
        return (
            f"Your daily protein target is {target} g. Suitable choices may include pulses, eggs, "
            "unsweetened yogurt, fish, chicken, tofu or paneer, adjusted for allergies and kidney status."
        )
    if any(term in text for term in ["sugar", "a1c", "diabetes", "glucose"]):
        return (
            "Distribute carbohydrate across meals, prefer minimally processed high-fibre choices, "
            "and pair them with protein. Insulin-treated diabetes or severe glucose results require professional review."
        )
    if any(term in text for term in ["kidney", "creatinine", "egfr", "potassium"]):
        return (
            "Kidney diets cannot be safely generated from one result. eGFR, potassium, medicines, fluid status "
            "and the full diagnosis must be reviewed by a qualified clinician."
        )
    if "plan" in text or "diet" in text:
        if not plan:
            return "Complete your profile or verify a laboratory report, then open Smart Diet Planner to generate a seven-day draft."
        status = "awaiting professional approval" if plan["status"] == "clinician-review" else "marked for general wellness"
        return (
            f"Your plan targets {plan['calories']} kcal, {plan['protein_g']} g protein and "
            f"{plan['fiber_g']} g fibre. It is {status}. Main focus: {', '.join(plan['focus'][:4])}."
        )
    if "weight" in text or "calorie" in text:
        return (
            f"Your current goal is {profile.get('goal', 'wellness')}. Energy targets use age, biological sex, "
            "height, weight and activity, then apply a conservative goal adjustment."
        )
    return (
        "I can explain your nutrition targets, verified laboratory-linked plan logic, protein, fibre, "
        "food substitutions, grocery planning and safety checks. I do not diagnose conditions or prescribe treatment."
    )
