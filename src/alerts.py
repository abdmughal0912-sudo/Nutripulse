from __future__ import annotations

import hashlib
import os
from datetime import datetime, time, timedelta, timezone
from typing import Any


SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Info": 3}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _signature(category: str, title: str, source: str) -> str:
    payload = f"{category}|{title}|{source}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _alert(
    severity: str,
    category: str,
    title: str,
    message: str,
    action: str,
    source: str,
) -> dict[str, Any]:
    return {
        "signature": _signature(category, title, source),
        "severity": severity,
        "category": category,
        "title": title,
        "message": message,
        "action": action,
        "source": source,
        "evaluated_at": _utc_now(),
    }


def evaluate_alerts(
    profile: dict[str, Any],
    labs: list[dict[str, Any]] | None = None,
    *,
    lab_verified: bool = True,
    plan_exists: bool = False,
    consumed_calories: float | None = None,
    target_calories: float | None = None,
    adherence_pct: float | None = None,
    water_l: float | None = None,
    model_health: dict[str, str] | None = None,
    meal_analysis: dict[str, Any] | None = None,
    meal_schedule: list[dict[str, Any]] | None = None,
    live_dietitians: list[dict[str, Any]] | None = None,
    local_now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return transparent in-app alerts without diagnosing or prescribing.

    Critical laboratory thresholds are inherited from the validated prototype
    rules in ``lab_analyzer``. Alerts are decision-support prompts: they never
    alter medication, diagnose a condition, or replace emergency services.
    """
    alerts: list[dict[str, Any]] = []
    labs = labs or []

    if labs and not lab_verified:
        alerts.append(_alert(
            "High", "Laboratory", "Laboratory values require verification",
            "Extracted report values may contain OCR, unit, or transcription errors.",
            "Compare every result with the original report before using it for planning.",
            "Unverified laboratory report",
        ))
    elif lab_verified:
        for row in labs:
            flag = str(row.get("flag", "")).lower()
            if flag not in {"critical", "high", "low", "unverified"}:
                continue
            test = str(row.get("test", "Laboratory result"))
            value = row.get("value", "—")
            unit = str(row.get("unit", "")).strip()
            reading = f"{value} {unit}".strip()
            if flag == "critical":
                alerts.append(_alert(
                    "Critical", "Laboratory", f"{test} needs urgent clinical review",
                    f"The verified value ({reading}) crossed a configured critical safety threshold.",
                    "Stop autonomous diet changes and contact a qualified clinician promptly. If you feel seriously unwell, use local emergency services.",
                    f"Verified {test}: {reading}",
                ))
            elif flag in {"high", "low"}:
                sensitive = test in {"Potassium", "Sodium", "eGFR", "Creatinine", "Haemoglobin", "Albumin"}
                alerts.append(_alert(
                    "High" if sensitive else "Medium",
                    "Laboratory",
                    f"{test} is outside the configured reference range",
                    f"The verified value ({reading}) was flagged {flag}. This flag is not a diagnosis.",
                    str(row.get("nutrition_note") or "Discuss the result with a qualified professional before therapeutic diet changes."),
                    f"Verified {test}: {reading}",
                ))
            else:
                alerts.append(_alert(
                    "Medium", "Laboratory", f"{test} has no validated alert rule",
                    "NutriPulse cannot safely interpret this result automatically.",
                    "Request professional interpretation and retain the original laboratory reference range.",
                    f"Unsupported {test}: {reading}",
                ))

    conditions = {str(item).strip().lower() for item in profile.get("conditions", []) if str(item).strip()}
    high_risk = {
        "advanced kidney disease", "advanced liver disease", "insulin-treated diabetes",
        "pregnancy", "eating disorder",
    }
    for condition in sorted(conditions & high_risk):
        display = condition.title()
        alerts.append(_alert(
            "High", "Clinical safety", f"Professional oversight required: {display}",
            "This profile requires individualized clinical nutrition assessment and monitoring.",
            "Use generated plans only as review drafts for a doctor or registered dietitian.",
            f"Profile condition: {condition}",
        ))

    allergies = [str(item).strip() for item in profile.get("allergies", []) if str(item).strip()]
    if allergies:
        alerts.append(_alert(
            "Medium", "Food safety", "Allergy and cross-contact safeguards are active",
            "Recorded sensitivities: " + ", ".join(allergies) + ".",
            "Verify ingredient labels, restaurant preparation, substitutions, and cross-contact every time.",
            "Patient allergy profile",
        ))

    for dietitian in live_dietitians or []:
        dietitian_id = str(dietitian.get("id") or dietitian.get("user_id") or "assigned")
        display_name = str(dietitian.get("display_name") or "Your assigned Dietitian").strip()
        credential = str(dietitian.get("credential") or "").strip()
        identity = f"{display_name} · {credential}" if credential else display_name
        alerts.append(_alert(
            "Info", "Care team", "DIETITIAN IS LIVE",
            f"{identity} is active in NutriPulse and available through your secure care workspace.",
            "Open Care Team to send a question or review your current recommendations.",
            f"Live assigned Dietitian: {dietitian_id}",
        ))

    if str(profile.get("medications", "")).strip():
        alerts.append(_alert(
            "Medium", "Medication safety", "Medication–food review is required",
            "The profile contains medicines or supplements, but NutriPulse does not modify or prescribe them.",
            "Ask a pharmacist, doctor, or dietitian to review timing, interactions, and supplement doses.",
            "Medication profile",
        ))

    if meal_analysis:
        vision = meal_analysis.get("vision") or {}
        predictions = vision.get("predictions") or []
        top_prediction = predictions[0] if predictions else {}
        confidence = float(top_prediction.get("confidence", 0) or 0)
        dish = str(meal_analysis.get("selected_label") or top_prediction.get("label") or "meal")
        if confidence < 0.35:
            alerts.append(_alert(
                "Medium", "Food vision", "Food image needs manual confirmation",
                f"The latest {dish} suggestion has only {confidence:.0%} model confidence.",
                "Use a clearer image or manually confirm the exact dish before using its nutrition estimate.",
                f"Latest Food Vision result: {dish}",
            ))
        if allergies:
            alerts.append(_alert(
                "High", "Food safety", "The image cannot verify recorded allergens",
                f"A photo of {dish} cannot reveal every ingredient or cross-contact risk.",
                "Confirm the full recipe, label and preparation process against the recorded allergy list before eating.",
                f"Food Vision allergy check: {dish}",
            ))
        nutrition = meal_analysis.get("nutrition") or {}
        calories = float(nutrition.get("calories", 0) or 0)
        sugar = float(nutrition.get("sugar_g", 0) or 0)
        sodium = float(nutrition.get("sodium_mg", 0) or 0)
        if calories >= 800:
            alerts.append(_alert(
                "Medium", "Meal estimate", "High estimated meal energy",
                f"The closest database record estimates {calories:.0f} kcal for the selected portion.",
                "Confirm the portion, oils, sauces and recipe before logging; avoid compensatory fasting.",
                f"Latest estimated meal: {dish}",
            ))
        if sodium >= 1_000:
            alerts.append(_alert(
                "High", "Meal estimate", "High estimated sodium in the selected portion",
                f"The database-linked estimate is {sodium:.0f} mg sodium.",
                "Confirm the exact product or recipe, especially when a clinician has advised sodium restriction.",
                f"Latest estimated meal sodium: {dish}",
            ))
        if sugar >= 40:
            alerts.append(_alert(
                "Medium", "Meal estimate", "High estimated sugar in the selected portion",
                f"The database-linked estimate is {sugar:.1f} g sugar.",
                "Confirm added sugars and portion size; use the result as an estimate, not a laboratory measurement.",
                f"Latest estimated meal sugar: {dish}",
            ))

    if conditions and not plan_exists:
        alerts.append(_alert(
            "Info", "Care pathway", "No active reviewed diet plan",
            "Medical conditions are recorded, but no current plan is active in this session.",
            "Verify relevant laboratory values, generate a review draft, and request professional approval.",
            "Diet plan status",
        ))

    offset = float(os.getenv("NUTRIPULSE_UTC_OFFSET_HOURS", "5") or 5)
    now = local_now or datetime.now(timezone(timedelta(hours=offset)))
    planned_today = [
        item for item in (meal_schedule or [])
        if str(item.get("scheduled_date")) == now.date().isoformat()
        and str(item.get("status", "Planned")) == "Planned"
    ]
    for item in planned_today:
        try:
            hour_text, minute_text = str(item.get("scheduled_time", "12:00")).split(":", 1)
            meal_at = datetime.combine(
                now.date(), time(int(hour_text), int(minute_text[:2])), tzinfo=now.tzinfo,
            )
        except (TypeError, ValueError):
            continue
        minutes = (meal_at - now).total_seconds() / 60
        meal_name = str(item.get("meal_name", "Planned meal"))
        display_time = meal_at.strftime("%I:%M %p").lstrip("0")
        source = f"Meal schedule {item.get('id', meal_name)}"
        if 0 <= minutes <= 30:
            alerts.append(_alert(
                "Info", "Meal schedule", f"{meal_name} is due at {display_time}",
                "Your personalized plan has a scheduled meal coming up.",
                "Open Today’s Schedule, review the portion, and mark the meal complete after eating.",
                source,
            ))
        elif -60 <= minutes < 0:
            alerts.append(_alert(
                "Medium", "Meal schedule", f"{meal_name} is waiting for completion",
                f"The planned time was {display_time}, and this meal is still marked Planned.",
                "Mark it Completed or Skipped so the adherence chart reflects what actually happened.",
                source,
            ))
        elif minutes < -60:
            alerts.append(_alert(
                "Medium", "Meal schedule", f"Update today’s {meal_name} status",
                f"The {display_time} plan item has not been cleared.",
                "Record Completed or Skipped; do not compensate with unsafe restriction.",
                source,
            ))

    if consumed_calories is not None and target_calories and target_calories > 0:
        ratio = float(consumed_calories) / float(target_calories)
        if ratio >= 1.30:
            alerts.append(_alert(
                "High", "Daily intake", "Daily energy is substantially above target",
                f"Logged intake is {ratio:.0%} of the current daily target.",
                "Review portions and missing context; do not compensate with fasting or unsafe restriction.",
                f"Confirmed food diary: {datetime.now(timezone.utc).date().isoformat()}",
            ))
        elif ratio >= 1.10:
            alerts.append(_alert(
                "Medium", "Daily intake", "Daily energy is above target",
                f"Logged intake is {ratio:.0%} of the current daily target.",
                "Review portion estimates and plan the remaining meals without extreme restriction.",
                f"Confirmed food diary: {datetime.now(timezone.utc).date().isoformat()}",
            ))

    if adherence_pct is not None:
        if adherence_pct < 50:
            alerts.append(_alert(
                "High", "Adherence", "Plan adherence needs support",
                f"The latest recorded adherence is {adherence_pct:.0f}%.",
                "Identify one practical barrier and discuss repeated difficulty with the care team.",
                f"Latest adherence measurement: {adherence_pct:.0f}%",
            ))
        elif adherence_pct < 75:
            alerts.append(_alert(
                "Medium", "Adherence", "Plan adherence is below goal",
                f"The latest recorded adherence is {adherence_pct:.0f}%.",
                "Choose a smaller, realistic next action and reassess at the next check-in.",
                f"Latest adherence measurement: {adherence_pct:.0f}%",
            ))

    if water_l is not None:
        if water_l < 1.2:
            alerts.append(_alert(
                "High", "Hydration", "Recorded hydration is very low",
                f"The latest entry is {water_l:.1f} L.",
                "Check measurement completeness. Fluid targets must be individualized for kidney, heart, or liver conditions.",
                f"Latest hydration measurement: {water_l:.1f} L",
            ))
        elif water_l < 1.8:
            alerts.append(_alert(
                "Medium", "Hydration", "Hydration is below the general wellness target",
                f"The latest entry is {water_l:.1f} L.",
                "Increase gradually only if a clinician has not prescribed fluid restriction.",
                f"Latest hydration measurement: {water_l:.1f} L",
            ))

    for component, state in (model_health or {}).items():
        if str(state).lower() not in {"ready", "ok", "verified"}:
            alerts.append(_alert(
                "Medium", "System", f"{component} requires attention",
                f"Current component status: {state}.",
                "Open Admin & MLOps, verify model files, and rerun the readiness check.",
                f"System component: {component}",
            ))

    return sorted(alerts, key=lambda item: (SEVERITY_ORDER.get(item["severity"], 99), item["category"], item["title"]))


def alert_counts(alerts: list[dict[str, Any]]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for alert in alerts:
        severity = str(alert.get("severity", "Info"))
        counts[severity] = counts.get(severity, 0) + 1
    counts["Total"] = len(alerts)
    return counts
