from __future__ import annotations

import hmac
import json
import os
from datetime import date
from functools import lru_cache
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from src.alerts import alert_counts, evaluate_alerts
from src.assistant import assistant_api_status, assistant_reply
from src.constants import APP_NAME, APP_VERSION, ASSET_DIR, DATA_DIR
from src.database import (
    acknowledge_alert, add_food_log, get_food_logs, initialize_database,
    get_schedule_progress, list_alerts, list_meal_schedule,
    set_meal_status_with_progress, upsert_profile,
)
from src.diet_engine import generate_plan
from src.food_analysis import analyze_food_image
from src.image_sources import RemoteImageError, fetch_public_image
from src.lab_analyzer import assess_safety, classify_manual_results
from src.ml_engine import MAX_MEAL_IMAGE_BYTES, food_vision_status, model_status, predict_food_image, predict_quality
from src.nutrition import load_food_data, search_foods
from src.web_insights import TRUSTED_SOURCES, WebInsightError, fetch_public_resource, fetch_trusted_article


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileInput(StrictModel):
    id: str = "api-profile"
    name: str = Field(default="API user", min_length=1, max_length=120)
    age: int = Field(default=30, ge=16, le=100)
    biological_sex: Literal["Male", "Female"] = "Male"
    height_cm: float = Field(default=170, ge=120, le=230)
    weight_kg: float = Field(default=70, ge=30, le=300)
    activity: Literal["Sedentary", "Lightly active", "Moderately active", "Very active", "Athlete"] = "Moderately active"
    goal: Literal["Fat loss", "Maintenance", "Weight gain", "Performance"] = "Maintenance"
    cuisine: Literal["Pakistani + international", "Pakistani", "Mediterranean", "Vegetarian", "Vegan"] = "Pakistani + international"
    conditions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    medications: str = ""


class LabValueInput(StrictModel):
    test: str = Field(min_length=1, max_length=80)
    value: float = Field(ge=0)
    unit: str = Field(default="", max_length=30)
    reference: str = Field(default="", max_length=80)


class LabAnalysisRequest(StrictModel):
    profile: ProfileInput = Field(default_factory=ProfileInput)
    values: list[LabValueInput] = Field(min_length=1, max_length=50)


class DietPlanRequest(StrictModel):
    profile: ProfileInput = Field(default_factory=ProfileInput)
    labs: list[LabValueInput] = Field(default_factory=list, max_length=50)


class QualityInput(StrictModel):
    food_name: str = Field(default="Custom food", min_length=1, max_length=160)
    food_type: str = Field(default="Other", min_length=1, max_length=80)
    calories: float = Field(ge=0, le=5000)
    protein_g: float = Field(default=0, ge=0, le=500)
    fat_g: float = Field(default=0, ge=0, le=500)
    carbs_g: float = Field(default=0, ge=0, le=1000)
    fiber_g: float = Field(default=0, ge=0, le=200)
    sugar_g: float = Field(default=0, ge=0, le=500)
    sodium_mg: float = Field(default=0, ge=0, le=50000)


class WebScrapeRequest(StrictModel):
    url: str = Field(min_length=8, max_length=2000)


class WebExtractRequest(WebScrapeRequest):
    headers: dict[str, str] = Field(default_factory=dict)


class VisionUrlRequest(StrictModel):
    url: str = Field(min_length=8, max_length=2000)
    servings: float = Field(default=1.0, ge=0.25, le=10)
    dish_hint: str | None = Field(default=None, max_length=160)


class AlertEvaluationRequest(StrictModel):
    profile: ProfileInput = Field(default_factory=ProfileInput)
    labs: list[LabValueInput] = Field(default_factory=list, max_length=50)
    lab_verified: bool = True
    plan_exists: bool = False
    consumed_calories: float | None = Field(default=None, ge=0, le=30000)
    target_calories: float | None = Field(default=None, ge=500, le=10000)
    adherence_pct: float | None = Field(default=None, ge=0, le=100)
    water_l: float | None = Field(default=None, ge=0, le=20)


class AssistantRequest(StrictModel):
    question: str = Field(min_length=2, max_length=2000)
    profile: ProfileInput = Field(default_factory=ProfileInput)
    plan: dict[str, Any] | None = None
    labs: list[LabValueInput] = Field(default_factory=list, max_length=50)
    use_external: bool = False


class DiaryVisionUrlRequest(VisionUrlRequest):
    profile: ProfileInput = Field(default_factory=ProfileInput)
    meal: Literal["Breakfast", "Lunch", "Dinner", "Snack"] = "Lunch"
    log_date: str | None = None


class MealStatusRequest(StrictModel):
    profile_id: str = Field(min_length=1, max_length=120)
    status: Literal["Planned", "Completed", "Skipped"]


@lru_cache(maxsize=1)
def food_frame():
    return load_food_data()


def configured_origins() -> list[str]:
    value = os.getenv(
        "NUTRIPULSE_CORS_ORIGINS",
        "http://localhost:8501,http://127.0.0.1:8501",
    )
    return [origin.strip() for origin in value.split(",") if origin.strip() and origin.strip() != "*"]


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("NUTRIPULSE_API_KEY", "").strip()
    if expected and (not x_api_key or not hmac.compare_digest(x_api_key, expected)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid X-API-Key header.")


app = FastAPI(
    title=f"{APP_NAME} API",
    version=APP_VERSION,
    summary="Nutrition intelligence, food vision, laboratory safety and protected public-data extraction API.",
    description=(
        "Clinical decision-support prototype. Responses are educational drafts and do not diagnose disease, "
        "prescribe medicines or replace a doctor or registered dietitian."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
initialize_database()


@app.get("/", tags=["service"])
def root() -> dict[str, Any]:
    return {
        "service": f"{APP_NAME} API",
        "version": APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "medical_scope": "Decision support only; not diagnosis or medical prescribing.",
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(ASSET_DIR / "nutripulse_mark.svg", media_type="image/svg+xml")


@app.get("/health", tags=["service"])
def health() -> dict[str, Any]:
    frame = food_frame()
    quality = model_status()
    vision = food_vision_status()
    manifest_path = DATA_DIR / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    source_audit = manifest.get("source_audit", {})
    return {
        "status": "ok" if len(frame) and vision.get("status") == "Ready" else "degraded",
        "version": APP_VERSION,
        "food_records": len(frame),
        "raw_source_records": source_audit.get("raw_source_records", len(frame)),
        "food_related_source_records": source_audit.get("food_related_source_records", len(frame)),
        "nutrition_classifier": quality.get("status"),
        "food_vision": vision.get("status"),
    }


@router.get("/foods/search", tags=["foods"])
def api_food_search(
    q: str = Query(default="", max_length=160),
    category: str = Query(default="All", max_length=80),
    max_calories: float | None = Query(default=None, ge=0, le=5000),
    min_protein: float = Query(default=0, ge=0, le=500),
    limit: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    result = search_foods(
        food_frame(), q, category, max_calories, min_protein,
        sort_by="healthy_rank_score", limit=limit,
    )
    return {"count": len(result), "items": json.loads(result.to_json(orient="records"))}


@router.post("/classifier/predict", tags=["machine-learning"])
def api_quality_predict(payload: QualityInput) -> dict[str, Any]:
    prediction = predict_quality(payload.model_dump())
    if prediction.get("status") != "ready":
        raise HTTPException(status_code=503, detail=prediction.get("message", "Classifier unavailable."))
    return prediction


@router.post("/labs/analyze", tags=["laboratory"])
def api_lab_analysis(payload: LabAnalysisRequest) -> dict[str, Any]:
    try:
        values = classify_manual_results([value.model_dump() for value in payload.values])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"results": values, "safety": assess_safety(values, payload.profile.model_dump())}


@router.post("/diet/plan", tags=["diet-planning"])
def api_diet_plan(payload: DietPlanRequest) -> dict[str, Any]:
    try:
        labs = classify_manual_results([value.model_dump() for value in payload.labs]) if payload.labs else []
        return generate_plan(payload.profile.model_dump(), labs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/vision/predict", tags=["deep-learning"])
async def api_vision_predict(
    image: Annotated[UploadFile, File(description="JPG, PNG or WebP meal image; maximum 10 MB")],
) -> dict[str, Any]:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG or WebP image.")
    image_bytes = await image.read(MAX_MEAL_IMAGE_BYTES + 1)
    await image.close()
    if len(image_bytes) > MAX_MEAL_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="The meal image exceeds the 10 MB inference limit.")
    try:
        prediction = predict_food_image(image_bytes)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if prediction.get("status") != "ready":
        raise HTTPException(status_code=503, detail=prediction.get("message", "Food vision unavailable."))
    return prediction


@router.post("/vision/analyze", tags=["deep-learning"])
async def api_vision_analyze(
    image: Annotated[UploadFile, File(description="JPG, PNG or WebP meal image; maximum 10 MB")],
    servings: Annotated[float, Form(ge=0.25, le=10)] = 1.0,
    dish_hint: Annotated[str | None, Form(max_length=160)] = None,
) -> dict[str, Any]:
    if image.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG or WebP image.")
    image_bytes = await image.read(MAX_MEAL_IMAGE_BYTES + 1)
    await image.close()
    if len(image_bytes) > MAX_MEAL_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="The meal image exceeds the 10 MB inference limit.")
    try:
        result = analyze_food_image(
            image_bytes, food_frame(), servings=servings,
            selected_label=dish_hint.strip() if dish_hint and dish_hint.strip() else None,
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("status") in {"error", "unavailable"}:
        raise HTTPException(status_code=503, detail=result.get("message", "Food analysis unavailable."))
    return result


@router.post("/vision/analyze-url", tags=["deep-learning"])
def api_vision_analyze_url(payload: VisionUrlRequest) -> dict[str, Any]:
    try:
        image_bytes, metadata = fetch_public_image(payload.url)
        result = analyze_food_image(
            image_bytes, food_frame(), servings=payload.servings,
            selected_label=payload.dish_hint.strip() if payload.dish_hint and payload.dish_hint.strip() else None,
        )
    except RemoteImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("status") in {"error", "unavailable"}:
        raise HTTPException(status_code=503, detail=result.get("message", "Food analysis unavailable."))
    result["source"] = metadata
    return result


@router.post("/diary/vision-url", tags=["food-diary"])
def api_diary_vision_url(payload: DiaryVisionUrlRequest) -> dict[str, Any]:
    try:
        image_bytes, metadata = fetch_public_image(payload.url)
        result = analyze_food_image(
            image_bytes, food_frame(), servings=payload.servings,
            selected_label=payload.dish_hint.strip() if payload.dish_hint and payload.dish_hint.strip() else None,
        )
    except RemoteImageError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result.get("status") != "ready":
        return {"logged": False, "analysis": result, "source": metadata}
    log_date = payload.log_date or date.today().isoformat()
    try:
        date.fromisoformat(log_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="log_date must use YYYY-MM-DD.") from exc
    profile_id = upsert_profile(payload.profile.model_dump())
    add_food_log(profile_id, log_date, payload.meal, result["nutrition_match"], payload.servings)
    return {"logged": True, "profile_id": profile_id, "log_date": log_date, "meal": payload.meal, "analysis": result, "source": metadata}


@router.get("/diary", tags=["food-diary"])
def api_diary_list(
    profile_id: str = Query(min_length=1, max_length=120),
    log_date: str | None = Query(default=None),
) -> dict[str, Any]:
    if log_date:
        try:
            date.fromisoformat(log_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="log_date must use YYYY-MM-DD.") from exc
    items = get_food_logs(profile_id, log_date)
    return {"count": len(items), "items": items}


@router.post("/assistant/ask", tags=["nutrition-assistant"])
def api_assistant(payload: AssistantRequest) -> dict[str, Any]:
    try:
        labs = classify_manual_results([value.model_dump() for value in payload.labs]) if payload.labs else []
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    reply = assistant_reply(
        payload.question, payload.profile.model_dump(), payload.plan, labs,
        use_external=payload.use_external,
    )
    return {
        "answer": reply["answer"],
        "intent": reply["intent"],
        "confidence": reply["confidence"],
        "grounding": reply["grounding"],
        "clinical_review_required": reply["clinical_review_required"],
        "suggested_actions": reply["suggested_actions"],
        "assistant": assistant_api_status(),
        "medical_scope": "Educational support only; not diagnosis, prescribing, or emergency care.",
    }


@router.get("/schedule", tags=["meal-schedule"])
def api_schedule(
    profile_id: str = Query(min_length=1, max_length=120),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    plan_id: str | None = Query(default=None),
) -> dict[str, Any]:
    items = list_meal_schedule(profile_id, date_from=date_from, date_to=date_to, plan_id=plan_id)
    return {
        "count": len(items),
        "items": items,
        "progress": get_schedule_progress(profile_id, plan_id),
    }


@router.post("/schedule/{meal_id}/status", tags=["meal-schedule"])
def api_schedule_status(meal_id: str, payload: MealStatusRequest) -> dict[str, Any]:
    result = set_meal_status_with_progress(meal_id, payload.profile_id, payload.status)
    if not result.get("updated"):
        raise HTTPException(status_code=404, detail="Scheduled meal not found for this profile.")
    return result


@router.post("/alerts/evaluate", tags=["alerts"])
def api_alert_evaluation(payload: AlertEvaluationRequest) -> dict[str, Any]:
    try:
        labs = classify_manual_results([value.model_dump() for value in payload.labs]) if payload.labs else []
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    alerts = evaluate_alerts(
        payload.profile.model_dump(), labs,
        lab_verified=payload.lab_verified,
        plan_exists=payload.plan_exists,
        consumed_calories=payload.consumed_calories,
        target_calories=payload.target_calories,
        adherence_pct=payload.adherence_pct,
        water_l=payload.water_l,
    )
    return {
        "alerts": alerts,
        "counts": alert_counts(alerts),
        "medical_scope": "Decision support only; alerts do not diagnose or prescribe.",
    }


@router.get("/alerts", tags=["alerts"])
def api_alert_list(
    profile_id: str = Query(default="default-profile", min_length=1, max_length=120),
    alert_status: Literal["Active", "Acknowledged", "Resolved"] | None = Query(default=None),
    include_resolved: bool = Query(default=False),
) -> dict[str, Any]:
    alerts = list_alerts(
        profile_id=profile_id, status=alert_status,
        include_resolved=include_resolved,
    )
    return {"count": len(alerts), "items": alerts}


@router.post("/alerts/{alert_id}/acknowledge", tags=["alerts"])
def api_alert_acknowledge(
    alert_id: str,
    profile_id: str = Query(default="default-profile", min_length=1, max_length=120),
) -> dict[str, Any]:
    if not acknowledge_alert(alert_id, profile_id):
        raise HTTPException(status_code=404, detail="Active alert not found.")
    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/web/sources", tags=["web-insights"])
def api_web_sources() -> dict[str, Any]:
    return {"count": len(TRUSTED_SOURCES), "sources": TRUSTED_SOURCES}


@router.post("/web/scrape", tags=["web-insights"])
def api_web_scrape(payload: WebScrapeRequest) -> dict[str, Any]:
    try:
        return fetch_trusted_article(payload.url)
    except WebInsightError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/web/extract", tags=["web-insights"])
def api_web_extract(payload: WebExtractRequest) -> dict[str, Any]:
    """Extract any public GET page or JSON/XML/text API without exposing private networks."""
    if len(payload.headers) > 10:
        raise HTTPException(status_code=422, detail="At most 10 session-only request headers are supported.")
    try:
        return fetch_public_resource(payload.url, request_headers=payload.headers)
    except WebInsightError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app.include_router(router)
