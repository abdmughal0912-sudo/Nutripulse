from __future__ import annotations

import html
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from src.alerts import alert_counts, evaluate_alerts
from src.assistant import answer_question, assistant_api_status
from src.auth import authenticate_with_status, register_account, register_admin_account
from src.constants import APP_NAME, APP_SUBTITLE, APP_VERSION, ASSET_DIR, DATA_DIR, SUPPORTED_LAB_TESTS
from src.database import (
    acknowledge_alert,
    acknowledge_all_alerts,
    add_clinical_note,
    add_clinical_prescription,
    add_food_log,
    add_measurement,
    create_meal_schedule,
    create_questionnaire,
    delete_food_log,
    get_food_logs,
    get_measurements,
    get_schedule_progress,
    has_admin,
    initialize_database,
    list_alerts,
    list_clinical_messages,
    list_clinical_notes,
    list_clinical_prescriptions,
    list_caseload_links,
    list_lab_reports,
    list_linked_customers,
    list_linked_dietitians,
    list_meal_schedule,
    list_plans,
    list_questionnaires,
    list_reviews,
    list_users,
    load_profile,
    link_dietitian_customer,
    request_review,
    save_lab_report,
    save_plan,
    send_clinical_message,
    set_caseload_assignment,
    set_dietitian_approval,
    set_meal_status_with_progress,
    set_prescription_status,
    submit_questionnaire,
    sync_alerts,
    upsert_profile,
)
from src.diet_engine import generate_plan, grocery_list
from src.food_analysis import analyze_food_image
from src.image_sources import RemoteImageError, fetch_public_image
from src.lab_analyzer import assess_safety, classify_manual_results, extract_text_from_upload, parse_lab_text
from src.ml_engine import food_vision_status, model_status, predict_quality, train_quality_model
from src.nutrition import (
    calculate_bmi, calculate_energy, dataset_quality, load_food_data,
    search_foods, search_foods_smart,
)
from src.reports import plan_to_csv, plan_to_json, plan_to_pdf
from src.theme import apply_theme, footer, hero, sidebar_brand
from src.web_insights import (
    TRUSTED_SOURCES, WebInsightError, allowed_domains, article_to_markdown,
    fetch_public_resource, fetch_trusted_article,
)


st.set_page_config(
    page_title=f"{APP_NAME} · Nutrition Analyzer",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()


initialize_database()


def admin_setup_code() -> str:
    configured = os.getenv("NUTRIPULSE_ADMIN_SETUP_CODE", "").strip()
    if configured:
        return configured
    try:
        secret = str(st.secrets.get("NUTRIPULSE_ADMIN_SETUP_CODE", "")).strip()
        if secret:
            return secret
    except Exception:
        pass
    return ""


def default_profile(profile_id: str, name: str) -> dict:
    return {
        "id": profile_id, "name": name, "age": 28,
        "biological_sex": "Male", "height_cm": 172.0, "weight_kg": 74.0,
        "activity": "Moderately active", "goal": "Fat loss",
        "cuisine": "Pakistani + international", "conditions": [],
        "allergies": [], "medications": "",
    }


def require_login() -> dict:
    existing = st.session_state.get("current_user")
    if existing:
        return existing
    st.markdown(
        '<div class="np-login-shell"><div class="np-login-mark">NP</div>'
        '<div><span>NUTRIPULSE PRIVATE HEALTH WORKSPACE</span>'
        '<h1>Clinical nutrition, beautifully secured.</h1>'
        '<p>One secure sign-in routes Customers, approved Dietitians and the Administrator into separate role-specific workspaces.</p></div></div>',
        unsafe_allow_html=True,
    )
    tab_names = ["Sign in", "Customer sign-up", "Dietitian application"]
    if not has_admin():
        tab_names.append("First admin setup")
    tabs = st.tabs(tab_names)
    sign_in, customer_register, dietitian_register = tabs[:3]
    with sign_in:
        with st.form("account_login"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Enter NutriPulse", type="primary", width="stretch")
        if submitted:
            user, message = authenticate_with_status(username, password)
            if user:
                st.session_state.current_user = user
                st.rerun()
            st.error(message)
    with customer_register:
        st.caption("Customer accounts are activated immediately and open only the personal nutrition workspace.")
        with st.form("customer_registration"):
            a, b = st.columns(2)
            display_name = a.text_input("Full name")
            b.text_input("Account type", "Customer", disabled=True)
            c, d = st.columns(2)
            new_username = c.text_input("Choose username")
            email = d.text_input("Email (optional)")
            e, f = st.columns(2)
            new_password = e.text_input("Choose password", type="password")
            confirm_password = f.text_input("Confirm password", type="password")
            create = st.form_submit_button("Create Customer account", type="primary", width="stretch")
        if create:
            try:
                if new_password != confirm_password:
                    raise ValueError("Passwords do not match.")
                user = register_account(new_username, new_password, "Customer", display_name, email)
                profile_payload = default_profile(str(user["id"]), str(user["display_name"]))
                upsert_profile(profile_payload)
                st.success("Customer account created. You can sign in now.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Account could not be created. The username may already exist.")
    with dietitian_register:
        st.info("Dietitian applications stay inactive until an Administrator verifies and approves the registration.")
        with st.form("dietitian_registration"):
            a, b = st.columns(2)
            dietitian_name = a.text_input("Full professional name")
            dietitian_credential = b.text_input("Registration / license ID")
            c, d = st.columns(2)
            dietitian_username = c.text_input("Choose username")
            dietitian_email = d.text_input("Professional email")
            e, f = st.columns(2)
            dietitian_password = e.text_input("Choose password", type="password")
            dietitian_confirm = f.text_input("Confirm password", type="password")
            apply = st.form_submit_button("Submit Dietitian application", type="primary", width="stretch")
        if apply:
            try:
                if dietitian_password != dietitian_confirm:
                    raise ValueError("Passwords do not match.")
                if len(dietitian_credential.strip()) < 3:
                    raise ValueError("A valid professional registration/license ID is required.")
                register_account(
                    dietitian_username, dietitian_password, "Dietitian", dietitian_name,
                    dietitian_email, dietitian_credential,
                )
                st.success("Application submitted. An Administrator must approve it before sign-in.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Application could not be submitted. The username may already exist.")
    if len(tabs) == 4:
        with tabs[3]:
            configured_admin_code = admin_setup_code()
            if not configured_admin_code:
                st.error(
                    "Administrator setup is disabled until NUTRIPULSE_ADMIN_SETUP_CODE "
                    "is configured privately in the environment or Streamlit secrets."
                )
                st.caption("Never place the real setup code in source control.")
            with st.form("first_admin_registration"):
                a, b = st.columns(2)
                admin_name = a.text_input("Administrator name")
                admin_email = b.text_input("Administrator email")
                c, d = st.columns(2)
                admin_username = c.text_input("Administrator username")
                setup_code = d.text_input("Local setup code", type="password")
                e, f = st.columns(2)
                admin_password = e.text_input("Administrator password", type="password")
                admin_confirm = f.text_input("Confirm administrator password", type="password")
                create_admin = st.form_submit_button(
                    "Create first Administrator", type="primary", width="stretch",
                    disabled=not configured_admin_code,
                )
            if create_admin:
                try:
                    if not configured_admin_code:
                        raise ValueError("Administrator setup code is not configured.")
                    if setup_code != configured_admin_code:
                        raise ValueError("Invalid Administrator setup code.")
                    if admin_password != admin_confirm:
                        raise ValueError("Passwords do not match.")
                    register_admin_account(admin_username, admin_password, admin_name, admin_email)
                    st.success("Administrator created. Sign in to approve Dietitians and assign customers.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    st.stop()


current_user = require_login()
is_admin = bool(int(current_user.get("is_admin", 0)))
sidebar_brand()
if current_user["role"] == "Dietitian":
    linked_customers = (
        [item for item in list_users("Customer") if int(item.get("active", 0))]
        if is_admin else list_linked_customers(str(current_user["id"]))
    )
else:
    linked_customers = []
if linked_customers:
    customer_options = {f"{item['display_name']} · @{item['username']}": item["id"] for item in linked_customers}
    chosen_customer = st.sidebar.selectbox("Active customer", list(customer_options), key="active_customer_selector")
    active_profile_id = str(customer_options[chosen_customer])
else:
    active_profile_id = str(current_user["id"])


@st.cache_data(show_spinner=False)
def food_data() -> pd.DataFrame:
    return load_food_data()


@st.cache_data(show_spinner=False, ttl=1800)
def cached_web_article(url: str) -> dict:
    return fetch_trusted_article(url)


def session_setup() -> None:
    profile_changed = st.session_state.get("session_profile_id") != active_profile_id
    if profile_changed:
        fallback_name = str(current_user["display_name"])
        if current_user["role"] == "Dietitian" and linked_customers:
            match = next((item for item in linked_customers if str(item["id"]) == active_profile_id), None)
            if match:
                fallback_name = str(match["display_name"])
        saved = load_profile(active_profile_id) or default_profile(active_profile_id, fallback_name)
        upsert_profile(saved)
        plans = list_plans(active_profile_id)
        latest_plan = plans[0] if plans else None
        st.session_state.profile = saved
        st.session_state.plan = latest_plan["plan"] if latest_plan else None
        st.session_state.plan_id = latest_plan["id"] if latest_plan else None
        st.session_state.lab_results = []
        st.session_state.lab_safety = {"level": "wellness", "reasons": [], "can_generate": True}
        st.session_state.lab_verified = False
        st.session_state.lab_report_id = None
        st.session_state.lab_editor_revision = 0
        st.session_state.vision_confirmed_dish_name = ""
        st.session_state.plan_active_date_requested = None
        st.session_state.schedule_transition_notice = None
        st.session_state.notified_critical_alerts = []
        st.session_state.chat = [
            {"role": "assistant", "content": "Hello — I can explain this nutrition profile, plan logic and safety checks. I do not diagnose conditions or change medicines."}
        ]
        st.session_state.session_profile_id = active_profile_id
    st.session_state.setdefault("lab_results", [])
    st.session_state.setdefault("lab_safety", {"level": "wellness", "reasons": [], "can_generate": True})
    st.session_state.setdefault("lab_verified", False)
    st.session_state.setdefault("lab_report_id", None)
    st.session_state.setdefault("lab_editor_revision", 0)
    st.session_state.setdefault("plan", None)
    st.session_state.setdefault("plan_id", None)
    st.session_state.setdefault("plan_active_date_requested", None)
    st.session_state.setdefault("schedule_transition_notice", None)
    st.session_state.setdefault("vision_predictions", None)
    st.session_state.setdefault("vision_signature", None)
    st.session_state.setdefault("vision_image_bytes", None)
    st.session_state.setdefault("vision_image_source", {})
    st.session_state.setdefault("last_food_analysis", None)
    st.session_state.setdefault("vision_confirmed_dish_name", "")
    st.session_state.setdefault("quality_result", None)
    st.session_state.setdefault("quality_input_name", None)
    st.session_state.setdefault("quality_input_food", None)
    st.session_state.setdefault("web_article", None)
    st.session_state.setdefault("notified_critical_alerts", [])
    st.session_state.setdefault("chat", [
        {"role": "assistant", "content": "Hello — I can explain your nutrition targets, plan logic and safety checks. I do not diagnose conditions or change medicines."}
    ])


session_setup()
frame = food_data()
profile = st.session_state.profile


@st.fragment(run_every="60s")
def live_schedule_watch() -> None:
    offset = float(os.getenv("NUTRIPULSE_UTC_OFFSET_HOURS", "5") or 5)
    now = datetime.now(timezone(timedelta(hours=offset)))
    meals = list_meal_schedule(
        active_profile_id, date_from=now.date().isoformat(), date_to=now.date().isoformat(),
    )
    due = []
    for meal in meals:
        if meal.get("status") != "Planned":
            continue
        try:
            hour, minute = str(meal["scheduled_time"]).split(":", 1)
            scheduled = now.replace(hour=int(hour), minute=int(minute[:2]), second=0, microsecond=0)
        except (TypeError, ValueError):
            continue
        difference = (scheduled - now).total_seconds() / 60
        if -60 <= difference <= 30:
            due.append((abs(difference), difference, meal, scheduled))
    if not due:
        return
    _, difference, meal, scheduled = sorted(due, key=lambda item: item[0])[0]
    state = "upcoming" if difference >= 0 else "waiting"
    token = f"{meal['id']}:{state}"
    notified = set(st.session_state.get("meal_popup_tokens", []))
    if token not in notified:
        phrase = "is due soon" if difference >= 0 else "is waiting to be cleared"
        st.toast(f"Meal reminder: {meal['meal_name']} {phrase}.", icon="⏰")
        notified.add(token)
        st.session_state.meal_popup_tokens = sorted(notified)
    st.sidebar.markdown(
        f'<div class="np-sidebar-alert"><span>⏰</span><div><strong>{html.escape(str(meal["meal_name"]))}</strong>'
        f'<small>{scheduled.strftime("%I:%M %p").lstrip("0")} · {state.title()}</small></div></div>',
        unsafe_allow_html=True,
    )


if current_user["role"] == "Customer" or linked_customers:
    live_schedule_watch()


def refresh_alert_state() -> list[dict]:
    energy = calculate_energy(profile)
    today_logs = get_food_logs(active_profile_id, date.today().isoformat())
    measurements = get_measurements(active_profile_id)
    week_start = date.today() - timedelta(days=date.today().weekday())
    schedule = list_meal_schedule(
        active_profile_id, date_from=week_start.isoformat(),
        date_to=(week_start + timedelta(days=6)).isoformat(),
    )
    latest = measurements[-1] if measurements else {}
    generated = evaluate_alerts(
        profile,
        st.session_state.lab_results,
        lab_verified=st.session_state.lab_verified,
        plan_exists=bool(st.session_state.plan),
        consumed_calories=sum(float(row["calories"]) for row in today_logs),
        target_calories=float(energy["target_calories"]),
        adherence_pct=latest.get("adherence_pct"),
        water_l=latest.get("water_l"),
        model_health={
            "Nutrition classifier": str(model_status().get("status", "Unavailable")),
            "Food vision": str(food_vision_status().get("status", "Unavailable")),
        },
        meal_analysis=st.session_state.get("last_food_analysis"),
        meal_schedule=schedule,
    )
    current = sync_alerts(generated, active_profile_id)
    notified = set(st.session_state.notified_critical_alerts)
    new_critical = [item for item in current if item["severity"] == "Critical" and item["status"] == "Active" and item["signature"] not in notified]
    if new_critical:
        st.toast(f"Critical safety alert: {new_critical[0]['title']}", icon="🚨")
        notified.update(item["signature"] for item in new_critical)
        st.session_state.notified_critical_alerts = sorted(notified)
    return current


current_alerts = refresh_alert_state() if current_user["role"] == "Customer" or linked_customers else []


def plot_layout(fig: go.Figure, height: int = 330) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=12, r=12, t=35, b=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9fb2ad"), legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor="rgba(207,244,231,.08)"),
        yaxis=dict(gridcolor="rgba(207,244,231,.08)"),
    )
    return fig


def frame_date_axis(fig: go.Figure, values: pd.Series, *, single_point_days: int = 3) -> go.Figure:
    """Keep sparse clinical charts readable instead of displaying microsecond ticks."""
    dates = pd.to_datetime(values).dropna()
    if dates.empty:
        return fig
    unique = dates.dt.normalize().drop_duplicates().sort_values()
    if len(unique) == 1:
        center = unique.iloc[0]
        fig.update_xaxes(
            range=[center - pd.Timedelta(days=single_point_days), center + pd.Timedelta(days=single_point_days)],
            dtick=24 * 60 * 60 * 1000,
            tickformat="%d %b\n%Y",
        )
    else:
        fig.update_xaxes(tickformat="%d %b\n%Y")
    return fig


def render_quality_result(prediction: dict, food_name: str, food: dict | None = None) -> None:
    if prediction.get("status") != "ready":
        st.error(prediction.get("message", "The nutrition classifier is unavailable."))
        return
    label = prediction["label"]
    st.markdown(
        f'<div class="np-classification" style="--result-color:{prediction["color"]}">'
        f'<span>ML NUTRITION CLASS</span><h3>{html.escape(prediction["title"])}</h3>'
        f'<p>{html.escape(prediction["summary"])}</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Prediction", label)
    c2.metric("Model confidence", f"{prediction['confidence']:.0%}")
    c3.metric("Food", str(food_name)[:35])
    probability_frame = pd.DataFrame({
        "Class": list(prediction["probabilities"]),
        "Probability": list(prediction["probabilities"].values()),
    })
    fig = px.bar(
        probability_frame, x="Probability", y="Class", orientation="h",
        color="Class", color_discrete_map={"Strong":"#b9f06a", "Balanced":"#5ce0d0", "Limit":"#ffb86b"},
        text=probability_frame["Probability"].map(lambda value: f"{value:.0%}"),
        title="Class probability",
    )
    fig.update_xaxes(range=[0, 1], tickformat=".0%")
    st.plotly_chart(plot_layout(fig, 250), width="stretch", config={"displayModeBar": False})
    if food:
        st.caption(
            f"Input per database serving · {float(food.get('calories', 0)):.0f} kcal · "
            f"protein {float(food.get('protein_g', 0)):.1f} g · fibre {float(food.get('fiber_g', 0)):.1f} g · "
            f"sugar {float(food.get('sugar_g', 0)):.1f} g · sodium {float(food.get('sodium_mg', 0)):.0f} mg"
        )
    st.info("This model classifies the nutrient profile only. It does not diagnose disease or decide whether a food is safe for a specific patient.")


def alert_card(alert: dict, *, compact: bool = False) -> None:
    severity = str(alert.get("severity", "Info"))
    css_class = severity.lower()
    action = "" if compact else f'<div class="np-alert-action"><b>Recommended next step</b>{html.escape(str(alert.get("action", "")))}</div>'
    st.markdown(
        f'<article class="np-alert-card {css_class}">'
        f'<div class="np-alert-card-top"><span class="np-severity">{html.escape(severity)}</span>'
        f'<span class="np-alert-state">{html.escape(str(alert.get("status", "Active")))}</span></div>'
        f'<h3>{html.escape(str(alert.get("title", "Alert")))}</h3>'
        f'<p>{html.escape(str(alert.get("message", "")))}</p>{action}'
        f'<small>{html.escape(str(alert.get("category", "Safety")))} · {html.escape(str(alert.get("source", "NutriPulse rules")))}</small>'
        f'</article>',
        unsafe_allow_html=True,
    )


def render_alert_preview(alerts: list[dict], limit: int = 3) -> None:
    active = [item for item in alerts if item.get("status") == "Active"]
    if not active:
        st.markdown(
            '<div class="np-all-clear"><span>✓</span><div><strong>No active safety alerts</strong>'
            '<small>NutriPulse is continuously checking current profile, verified labs, diary and progress signals.</small></div></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown('<div class="np-section-kicker">Priority alert feed</div>', unsafe_allow_html=True)
    for item in active[:limit]:
        alert_card(item, compact=True)


def schedule_completion(schedule: list[dict]) -> tuple[int, int, float]:
    completed = sum(str(item.get("status")) == "Completed" for item in schedule)
    total = len(schedule)
    return completed, total, (completed / total * 100 if total else 0.0)


def schedule_analytics(schedule: list[dict], plan_names: dict[str, str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not schedule:
        return pd.DataFrame(), pd.DataFrame()
    data = pd.DataFrame(schedule).copy()
    data["scheduled_date"] = pd.to_datetime(data["scheduled_date"])
    data["plan_start"] = data.groupby("plan_id")["scheduled_date"].transform("min")
    data["week_number"] = ((data["scheduled_date"] - data["plan_start"]).dt.days // 7 + 1).astype(int)
    data["completed_value"] = (data["status"] == "Completed").astype(int)
    data["skipped_value"] = (data["status"] == "Skipped").astype(int)
    data["total_value"] = 1
    daily = data.groupby(
        ["plan_id", "week_number", "scheduled_date", "day_name"], as_index=False,
    )[["completed_value", "skipped_value", "total_value"]].sum()
    daily["completion_pct"] = (daily["completed_value"] / daily["total_value"].clip(lower=1) * 100).round(1)
    daily["status"] = "Upcoming"
    daily.loc[(daily["completed_value"] > 0) | (daily["skipped_value"] > 0), "status"] = "In progress"
    daily.loc[daily["completed_value"] == daily["total_value"], "status"] = "Completed"
    daily["day_label"] = daily.apply(
        lambda row: f"W{int(row['week_number'])} · {row['day_name']} · {row['scheduled_date'].strftime('%d %b')}",
        axis=1,
    )
    weekly = data.groupby(["plan_id", "week_number"], as_index=False).agg(
        week_start=("scheduled_date", "min"),
        week_end=("scheduled_date", "max"),
        completed=("completed_value", "sum"),
        skipped=("skipped_value", "sum"),
        total=("total_value", "sum"),
    )
    weekly["completion_pct"] = (weekly["completed"] / weekly["total"].clip(lower=1) * 100).round(1)
    weekly["status"] = "Upcoming"
    weekly.loc[(weekly["completed"] > 0) | (weekly["skipped"] > 0), "status"] = "In progress"
    weekly.loc[weekly["completed"] == weekly["total"], "status"] = "Completed"
    names = plan_names or {}
    weekly["plan_name"] = weekly["plan_id"].map(names).fillna("Diet plan")
    weekly["week_label"] = weekly.apply(
        lambda row: f"{row['plan_name']} · Week {int(row['week_number'])}", axis=1,
    )
    return daily, weekly


def render_schedule_rows(schedule: list[dict], key_prefix: str, *, interactive: bool = True) -> None:
    if not schedule:
        st.info("No meal schedule is saved for this date. Generate a plan to create it.")
        return
    for item in schedule:
        status = str(item.get("status", "Planned"))
        body, action, skip = st.columns([5.2, 1.15, 1.0])
        with body:
            st.markdown(
                f'<div class="np-meal np-meal-{status.lower()}"><time>{html.escape(str(item["scheduled_time"]))}</time>'
                f'<div><strong>{html.escape(str(item["meal_name"]))}</strong>'
                f'<small>{html.escape(str(item["meal_detail"]))}</small></div>'
                f'<span><b>{float(item["calories"]):.0f}</b> kcal<br><small>{html.escape(status)}</small></span></div>',
                unsafe_allow_html=True,
            )
        with action:
            label = "Undo" if status == "Completed" else "Clear meal ✓"
            target = "Planned" if status == "Completed" else "Completed"
            if st.button(
                label, key=f"{key_prefix}_complete_{item['id']}",
                width="stretch", disabled=not interactive,
            ):
                result = set_meal_status_with_progress(str(item["id"]), active_profile_id, target)
                if result.get("day_completed"):
                    next_date = result.get("next_active_date")
                    completed_week = result.get("completed_week_number")
                    if completed_week:
                        notice = (
                            f"Week {completed_week} completed — excellent consistency. "
                            f"Week {completed_week + 1} is ready and your progress history has been preserved."
                        )
                    else:
                        day_name = str(item.get("day_name", "Day"))
                        notice = f"{day_name} completed. NutriPulse moved your schedule to the next active day."
                    st.session_state.schedule_transition_notice = notice
                    st.session_state.plan_active_date_requested = next_date
                    if key_prefix == "dashboard":
                        st.session_state.workspace_page_requested = "▦  Smart Diet Planner"
                elif target != "Completed":
                    st.session_state.plan_active_date_requested = result.get("next_active_date")
                st.rerun()
        with skip:
            if status != "Skipped" and st.button(
                "Skip", key=f"{key_prefix}_skip_{item['id']}",
                width="stretch", disabled=not interactive,
            ):
                result = set_meal_status_with_progress(str(item["id"]), active_profile_id, "Skipped")
                st.session_state.plan_active_date_requested = result.get("next_active_date")
                st.rerun()
            elif status == "Skipped" and st.button(
                "Restore", key=f"{key_prefix}_restore_{item['id']}",
                width="stretch", disabled=not interactive,
            ):
                result = set_meal_status_with_progress(str(item["id"]), active_profile_id, "Planned")
                st.session_state.plan_active_date_requested = result.get("next_active_date")
                st.rerun()


def render_dashboard() -> None:
    energy = calculate_energy(profile)
    bmi, bmi_label = calculate_bmi(profile["weight_kg"], profile["height_cm"])
    logs = get_food_logs(active_profile_id, date.today().isoformat())
    consumed = sum(row["calories"] for row in logs)
    protein = sum(row["protein_g"] for row in logs)
    fibre = sum(row["fiber_g"] for row in logs)
    remaining = max(0, energy["target_calories"] - consumed)
    hero(
        "Personal nutrition workspace",
        f"Good day, {html.escape(profile['name'])}.<br><em>Your health data, in rhythm.</em>",
        "One intelligent workspace for food analysis, laboratory-linked planning, progress monitoring and professional review.",
        f"{len(frame):,} verified food records connected",
    )
    dashboard_visual = ASSET_DIR / "nutripulse_hero.jpg"
    if dashboard_visual.exists():
        st.image(
            str(dashboard_visual),
            caption="NutriPulse nutrition intelligence · original bundled artwork",
            width="stretch",
        )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Daily energy", f"{consumed:,.0f}", f"{remaining:,.0f} kcal remaining")
    c2.metric("Protein", f"{protein:.0f} g", f"Target {round(energy['target_calories']*.25/4)} g")
    c3.metric("Fibre", f"{fibre:.0f} g", "Target 32 g")
    c4.metric("BMI", bmi, bmi_label)
    c5.metric("Safety", st.session_state.lab_safety["level"].replace("-", " ").title(), "Rules active")
    st.progress(min(1.0, consumed / energy["target_calories"] if energy["target_calories"] else 0), text="Daily energy progress")
    render_alert_preview(current_alerts, limit=2)

    plan_progress = get_schedule_progress(active_profile_id, st.session_state.plan_id)
    active_schedule_date = plan_progress.get("active_date") or date.today().isoformat()
    today_schedule = list_meal_schedule(
        active_profile_id, date_from=active_schedule_date, date_to=active_schedule_date,
        plan_id=st.session_state.plan_id,
    ) if st.session_state.plan_id else []
    completed, scheduled, completion_pct = schedule_completion(today_schedule)
    if scheduled:
        active_day = next(
            (item for item in plan_progress.get("days", []) if item["scheduled_date"] == active_schedule_date),
            {},
        )
        st.progress(
            completion_pct / 100,
            text=(
                f"Week {active_day.get('week_number', 1)} · {active_day.get('day_name', 'Active day')} "
                f"completion · {completed}/{scheduled} meals ({completion_pct:.0f}%)"
            ),
        )

    left, right = st.columns([1.45, 1])
    with left:
        st.markdown(
            '<div class="np-panel"><div class="np-eyebrow">ACTIVE SCHEDULE DAY</div>'
            f'<h3>{html.escape(str(active_schedule_date))} · Precision meal plan</h3>',
            unsafe_allow_html=True,
        )
        render_schedule_rows(today_schedule, "dashboard")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="np-panel"><div class="np-eyebrow">LIVE ANALYSIS</div><h3>Nutrition signal</h3>', unsafe_allow_html=True)
        macros = pd.DataFrame({"Nutrient": ["Protein", "Carbohydrate", "Fat"], "Grams": [protein, sum(row["carbs_g"] for row in logs), sum(row["fat_g"] for row in logs)]})
        fig = px.pie(macros, names="Nutrient", values="Grams", hole=.72, color="Nutrient", color_discrete_map={"Protein":"#b9f06a","Carbohydrate":"#5ce0d0","Fat":"#a78bfa"})
        fig.update_traces(textinfo="percent", hovertemplate="%{label}: %{value:.1f}g<extra></extra>")
        st.plotly_chart(plot_layout(fig, 260), width="stretch", config={"displayModeBar": False})
        st.markdown("</div>", unsafe_allow_html=True)
    week_start = date.today() - timedelta(days=date.today().weekday())
    history_start = week_start - timedelta(days=21)
    future_end = week_start + timedelta(days=20)
    schedule_window = list_meal_schedule(
        active_profile_id, date_from=history_start.isoformat(), date_to=future_end.isoformat(),
    )
    if schedule_window:
        schedule_frame = pd.DataFrame(schedule_window)
        schedule_frame["scheduled_date"] = pd.to_datetime(schedule_frame["scheduled_date"])
        daily = schedule_frame.groupby(["scheduled_date", "status"]).size().reset_index(name="Meals")
        fig = px.bar(
            daily, x="scheduled_date", y="Meals", color="status", barmode="stack",
            title="Past records and future meal schedule",
            color_discrete_map={"Completed": "#b9f06a", "Planned": "#5ce0d0", "Skipped": "#ffb86b"},
        )
        st.plotly_chart(plot_layout(fig, 290), width="stretch", config={"displayModeBar": False})
    if any(item["severity"] == "Critical" and item["status"] == "Active" for item in current_alerts):
        st.error("A critical safety gate is active. Open Alert Center and Laboratory Intelligence before generating or changing a plan.")


def render_alert_center() -> None:
    hero(
        "Real-time safety command center",
        "Every important signal.<br><em>One calm place to act.</em>",
        "NutriPulse continuously evaluates verified laboratory results, profile risks, food safety, daily intake, hydration, adherence and model readiness.",
        "In-app alerts · persistent history · acknowledgement workflow",
    )
    history = list_alerts(active_profile_id, include_resolved=True)
    current = [item for item in history if item["status"] != "Resolved"]
    active = [item for item in current if item["status"] == "Active"]
    counts = alert_counts(current)
    columns = st.columns(5)
    columns[0].metric("Active alerts", len(active), "Needs review")
    columns[1].metric("Critical", counts.get("Critical", 0), "Urgent safety gate")
    columns[2].metric("High", counts.get("High", 0), "Prompt action")
    columns[3].metric("Medium", counts.get("Medium", 0), "Monitor or review")
    columns[4].metric("Acknowledged", sum(item["status"] == "Acknowledged" for item in current), "Retained in history")

    command_left, command_right = st.columns([1.5, .5])
    with command_left:
        severity_filter = st.multiselect(
            "Severity", ["Critical", "High", "Medium", "Info"],
            default=["Critical", "High", "Medium", "Info"],
            key="alert_severity_filter",
        )
    with command_right:
        status_filter = st.selectbox("Status", ["Current", "Active", "Acknowledged", "Resolved", "All"])

    filtered = [item for item in history if item["severity"] in severity_filter]
    if status_filter == "Current":
        filtered = [item for item in filtered if item["status"] != "Resolved"]
    elif status_filter != "All":
        filtered = [item for item in filtered if item["status"] == status_filter]

    action_columns = st.columns([1, 1, 2])
    if action_columns[0].button("Refresh alert rules", type="primary", width="stretch"):
        st.rerun()
    if action_columns[1].button("Acknowledge all active", disabled=not active, width="stretch"):
        acknowledged = acknowledge_all_alerts(active_profile_id)
        st.toast(f"Acknowledged {acknowledged} alert(s).", icon="✓")
        st.rerun()
    action_columns[2].markdown(
        '<div class="np-command-note"><b>Alert delivery:</b> This edition provides secure in-app notifications. '
        'It does not send patient data to email, SMS, or third-party services.</div>',
        unsafe_allow_html=True,
    )

    if not filtered:
        st.markdown(
            '<div class="np-all-clear premium"><span>✓</span><div><strong>Your selected alert view is clear</strong>'
            '<small>Change the status or severity filters to inspect alert history.</small></div></div>',
            unsafe_allow_html=True,
        )
    for item in filtered:
        body, control = st.columns([5.5, 1])
        with body:
            alert_card(item)
        with control:
            st.write("")
            st.caption(item["updated_at"].replace("T", " ")[:16] + " UTC")
            if item["status"] == "Active":
                if st.button("Acknowledge", key=f"ack_{item['id']}", width="stretch"):
                    acknowledge_alert(item["id"], active_profile_id)
                    st.rerun()
            else:
                st.markdown(f'<span class="np-status-pill">{html.escape(item["status"])}</span>', unsafe_allow_html=True)

    with st.expander("Alert rules and clinical boundaries"):
        rules = pd.DataFrame([
            ["Critical", "Verified critical laboratory threshold", "Stop autonomous planning; urgent clinical review"],
            ["High", "Sensitive abnormal lab, high-risk condition, very low adherence/hydration", "Prompt review and professional escalation"],
            ["Medium", "Other abnormal lab, allergy, medicine, moderate intake/adherence signal", "Monitor, verify, and take a safe next step"],
            ["Info", "Care-pathway or plan-status reminder", "Complete the recommended workflow"],
        ], columns=["Severity", "Typical trigger", "System behavior"])
        st.dataframe(rules, width="stretch", hide_index=True)
        st.warning("Alerts are decision support, not diagnoses. NutriPulse never changes medication or replaces emergency assessment.")


def render_profile() -> None:
    hero("Personalization", "Build your <em>clinical-safe profile.</em>", "These inputs drive transparent energy calculations, plan constraints and safety checks.")
    with st.form("profile_form"):
        c1, c2, c3 = st.columns(3)
        name = c1.text_input("Full name", profile["name"])
        age = c2.number_input("Age", 16, 100, int(profile["age"]))
        sex = c3.selectbox("Biological sex", ["Male", "Female"], index=0 if profile["biological_sex"] == "Male" else 1)
        c4, c5, c6 = st.columns(3)
        height = c4.number_input("Height (cm)", 120.0, 230.0, float(profile["height_cm"]), .5)
        weight = c5.number_input("Weight (kg)", 30.0, 300.0, float(profile["weight_kg"]), .5)
        activity_options = ["Sedentary", "Lightly active", "Moderately active", "Very active", "Athlete"]
        activity = c6.selectbox("Activity level", activity_options, index=activity_options.index(profile["activity"]) if profile["activity"] in activity_options else 2)
        c7, c8 = st.columns(2)
        goal_options = ["Fat loss", "Maintenance", "Weight gain", "Performance"]
        goal = c7.selectbox("Goal", goal_options, index=goal_options.index(profile["goal"]) if profile["goal"] in goal_options else 0)
        cuisine_options = ["Pakistani + international", "Pakistani", "Mediterranean", "Vegetarian", "Vegan"]
        cuisine = c8.selectbox(
            "Cuisine", cuisine_options,
            index=cuisine_options.index(profile["cuisine"]) if profile.get("cuisine") in cuisine_options else 0,
        )
        condition_options = ["Diabetes", "Hypertension", "Dyslipidaemia", "PCOS", "Fatty liver", "Gout", "Advanced kidney disease", "Advanced liver disease", "Insulin-treated diabetes", "Pregnancy", "Eating disorder"]
        conditions = st.multiselect("Medical conditions", condition_options, default=profile.get("conditions", []))
        allergies = st.multiselect("Food allergies/intolerances", ["Peanuts", "Tree nuts", "Milk", "Egg", "Fish", "Shellfish", "Wheat/gluten", "Soy", "Lactose"], default=profile.get("allergies", []))
        medications = st.text_area("Medicines and supplements (for professional review)", profile.get("medications", ""))
        submitted = st.form_submit_button("Save clinical profile", type="primary", width="stretch")
    if submitted:
        updated = {"id":active_profile_id,"name":name,"age":age,"biological_sex":sex,"height_cm":height,"weight_kg":weight,"activity":activity,"goal":goal,"cuisine":cuisine,"conditions":conditions,"allergies":allergies,"medications":medications}
        upsert_profile(updated)
        st.session_state.profile = updated
        if st.session_state.lab_results and st.session_state.lab_verified:
            st.session_state.lab_safety = assess_safety(st.session_state.lab_results, updated)
        elif st.session_state.lab_results:
            st.session_state.lab_safety = {
                "level": "unverified", "reasons": ["Laboratory values require confirmation"],
                "can_generate": False,
            }
        st.session_state.plan = None
        st.session_state.plan_id = None
        st.success("Profile saved. Energy, plan and safety calculations are updated.")
        st.rerun()
    energy = calculate_energy(profile)
    bmi, label = calculate_bmi(profile["weight_kg"], profile["height_cm"])
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("BMI", bmi, label)
    m2.metric("BMR", f"{energy['bmr']} kcal", "Resting estimate")
    m3.metric("TDEE", f"{energy['tdee']} kcal", "Maintenance estimate")
    m4.metric("Plan target", f"{energy['target_calories']} kcal", profile["goal"])


def render_labs(*, clinical_mode: bool = False) -> None:
    if clinical_mode:
        hero(
            "Clinical report analysis",
            "Analyze the selected customer.<br><em>Then build a safety-gated plan.</em>",
            "Upload or review a laboratory report, verify every extracted value, and connect the result to Dietitian plan oversight.",
            "Dietitian verification required",
        )
    else:
        hero("Laboratory intelligence", "Turn a report into<br><em>safe nutrition action.</em>", "Upload an image or PDF, verify every extracted value, and pass it through clinical safety rules before plan generation.", "Human verification required")
    upload_col, guide_col = st.columns([1.35, .65])
    with upload_col:
        uploaded = st.file_uploader("Upload laboratory report", type=["png", "jpg", "jpeg", "webp", "pdf"], help="Maximum size follows your Streamlit configuration.")
        c1, c2 = st.columns(2)
        if c1.button("Extract report values", type="primary", disabled=uploaded is None, width="stretch"):
            try:
                with st.spinner("Reading the report…"):
                    text, method = extract_text_from_upload(uploaded)
                st.session_state.lab_raw_text = text
                parsed = parse_lab_text(text)
                st.session_state.lab_results = parsed
                st.session_state.lab_verified = False
                st.session_state.lab_report_id = None
                st.session_state.lab_safety = {
                    "level": "unverified", "reasons": ["Laboratory values require confirmation"],
                    "can_generate": False,
                }
                st.session_state.lab_method = method
                st.session_state.lab_editor_revision += 1
                if parsed:
                    st.success(f"Found {len(parsed)} supported values using {method}. Verify them below.")
                else:
                    st.warning(f"No supported values were reliably extracted. {method}. Enter results manually below.")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        if c2.button("Load safe demonstration report", width="stretch"):
            demo = "HbA1c 6.1 % LDL cholesterol 142 mg/dL Vitamin D 19 ng/mL Haemoglobin 13.8 g/dL eGFR 92 Potassium 4.2 mmol/L"
            st.session_state.lab_raw_text = demo
            st.session_state.lab_results = parse_lab_text(demo)
            st.session_state.lab_method = "Demonstration dataset"
            st.session_state.lab_verified = False
            st.session_state.lab_report_id = None
            st.session_state.lab_editor_revision += 1
            st.session_state.lab_safety = {
                "level": "unverified", "reasons": ["Demonstration values require confirmation"],
                "can_generate": False,
            }
            st.rerun()
        if uploaded and uploaded.type.startswith("image"):
            st.image(uploaded, caption="Uploaded laboratory report", width="stretch")
    with guide_col:
        laboratory_visual = ASSET_DIR / "lab_nutrition.jpg"
        if laboratory_visual.exists():
            st.image(str(laboratory_visual), caption="Laboratory-aware nutrition review", width="stretch")
        st.markdown('<div class="np-panel"><div class="np-eyebrow">SUPPORTED EXTRACTION</div><h3>Nutrition-relevant tests</h3><p>' + " · ".join(SUPPORTED_LAB_TESTS) + '</p></div>', unsafe_allow_html=True)
        st.markdown('<div class="np-alert"><span>✦</span><div><strong>OCR is never the final authority</strong><br><small>Compare every value, unit and reference range with the original report.</small></div></div>', unsafe_allow_html=True)
    if hasattr(st.session_state, "lab_raw_text"):
        if st.session_state.get("lab_method"):
            st.caption(f"Extraction method: {st.session_state.lab_method}")
        with st.expander("Extracted report text"):
            st.text_area(
                "OCR/PDF text", st.session_state.lab_raw_text, height=160,
                key=f"lab_text_review_{st.session_state.lab_editor_revision}",
            )

    initial = st.session_state.lab_results or [
        {"test":"HbA1c","value":"","unit":"%","reference":"4.0–5.6"},
        {"test":"LDL cholesterol","value":"","unit":"mg/dL","reference":"<100"},
    ]
    editor_frame = pd.DataFrame(initial)[[column for column in ["test","value","unit","reference"] if column in pd.DataFrame(initial).columns]]
    st.subheader("Verify or enter laboratory values")
    edited = st.data_editor(
        editor_frame, num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "test": st.column_config.TextColumn("Test", required=True, help="Known and additional laboratory test names are accepted."),
            "value": st.column_config.NumberColumn("Result", format="%.3f", required=True),
        },
        key=f"lab_value_editor_{st.session_state.lab_editor_revision}",
    )
    if st.button("Confirm values and run safety analysis", type="primary", width="stretch"):
        try:
            results = classify_manual_results(edited.to_dict("records"))
            if not results:
                raise ValueError("Enter at least one complete test result.")
            safety = assess_safety(results, profile)
            report_name = uploaded.name if uploaded else "manual-or-demonstration-report"
            report_id = save_lab_report(
                report_name, results, safety["level"],
                profile_id=active_profile_id,
                reviewed_by=str(current_user["display_name"]),
            )
            st.session_state.lab_results = results
            st.session_state.lab_safety = safety
            st.session_state.lab_verified = True
            st.session_state.lab_report_id = report_id
            st.success("Values verified and safety analysis completed.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if st.session_state.lab_results:
        results = pd.DataFrame(st.session_state.lab_results)
        st.dataframe(results[["test","value","unit","reference","flag","nutrition_note"]], width="stretch", hide_index=True)
        safety = st.session_state.lab_safety
        if not st.session_state.lab_verified:
            st.info("These values are unverified. Confirm them above before generating a laboratory-linked plan.")
        elif not safety["can_generate"]:
            st.markdown('<div class="np-alert danger"><span>!</span><div><strong>Automatic therapeutic planning stopped</strong><br><small>' + html.escape("; ".join(safety["reasons"])) + '</small></div></div>', unsafe_allow_html=True)
        elif safety["level"] == "clinician-review":
            st.markdown('<div class="np-alert warning"><span>✦</span><div><strong>Plan may be generated as a professional-review draft</strong><br><small>Abnormal values were detected. This is not a diagnosis.</small></div></div>', unsafe_allow_html=True)
        else:
            st.success("No configured high-risk gate was triggered. General wellness planning is available.")


def render_plan() -> None:
    hero("Constraint-based recommendation engine", "A seven-day plan<br><em>built around your real life.</em>", "Energy, laboratory signals, conditions, allergies, cuisine and food-quality rules are considered together.")
    safety = st.session_state.lab_safety
    c1, c2 = st.columns([1, 1])
    generate_disabled = not safety.get("can_generate", True)
    if c1.button("Generate personalized full diet plan", type="primary", disabled=generate_disabled, width="stretch"):
        try:
            plan = generate_plan(profile, st.session_state.lab_results)
            plan_id = save_plan(active_profile_id, plan, st.session_state.lab_report_id)
            week_start = date.today() - timedelta(days=date.today().weekday())
            create_meal_schedule(active_profile_id, plan_id, plan, week_start.isoformat())
            st.session_state.plan = plan
            st.session_state.plan_id = plan_id
            st.success("Seven-day plan generated and saved.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if c2.button("Generate wellness-only plan without laboratory values", disabled=bool(profile.get("conditions")), width="stretch"):
        try:
            plan = generate_plan(profile, [])
            plan_id = save_plan(active_profile_id, plan)
            week_start = date.today() - timedelta(days=date.today().weekday())
            create_meal_schedule(active_profile_id, plan_id, plan, week_start.isoformat())
            st.session_state.plan = plan
            st.session_state.plan_id = plan_id
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    plan = st.session_state.plan
    if not plan:
        st.markdown('<div class="np-panel"><h3>No plan generated yet</h3><p>Complete your profile, verify relevant laboratory values, then generate a transparent seven-day draft.</p></div>', unsafe_allow_html=True)
        return
    a, b, c, d, e, f = st.columns(6)
    a.metric("Energy", f"{plan['calories']} kcal")
    b.metric("Protein", f"{plan['protein_g']} g")
    c.metric("Carbs", f"{plan['carbs_g']} g")
    d.metric("Fat", f"{plan['fat_g']} g")
    e.metric("Fibre", f"{plan['fiber_g']} g")
    f.metric("Water", f"{plan['water_l']} L")
    status_text = "Professional review required" if plan["status"] == "clinician-review" else "General wellness plan"
    st.markdown(f'<span class="np-badge"><i class="np-dot"></i>{status_text}</span>', unsafe_allow_html=True)
    st.write("**Plan focus:** " + " · ".join(plan["focus"]))
    if plan.get("dietary_constraints"):
        st.warning(plan["cross_contact_notice"])
    notice = st.session_state.pop("schedule_transition_notice", None)
    if notice:
        st.success(str(notice))
    progress = get_schedule_progress(active_profile_id, st.session_state.plan_id)
    saved_schedule = list_meal_schedule(
        active_profile_id, plan_id=st.session_state.plan_id,
    ) if st.session_state.plan_id else []
    if saved_schedule and progress.get("days"):
        week_columns = st.columns(min(4, max(1, len(progress["weeks"]))))
        for column, week in zip(week_columns, progress["weeks"][-4:]):
            column.metric(
                f"Week {week['week_number']} · {week['status']}",
                f"{week['completion_pct']:.0f}%",
                f"{week['completed']}/{week['total']} meals",
            )
        day_options = [str(item["scheduled_date"]) for item in progress["days"]]
        day_by_date = {str(item["scheduled_date"]): item for item in progress["days"]}
        active_date = str(progress.get("active_date") or day_options[-1])
        selector_key = f"plan_day_selector_{st.session_state.plan_id}"
        requested_date = st.session_state.pop("plan_active_date_requested", None)
        if requested_date in day_options:
            st.session_state[selector_key] = requested_date
        elif st.session_state.get(selector_key) not in day_options:
            st.session_state[selector_key] = active_date

        def day_label(value: str) -> str:
            item = day_by_date[value]
            marker = "✓" if item["status"] == "Completed" else "●" if value == active_date else "○"
            return (
                f"{marker} Week {item['week_number']} · {item['day_name']} · "
                f"{item['completion_pct']:.0f}% · {value}"
            )

        selected_date = st.selectbox(
            "Schedule day",
            day_options,
            key=selector_key,
            format_func=day_label,
            help="Completed days stay available as history. Future days unlock in sequence.",
        )
        selected_day = day_by_date[selected_date]
        day_schedule = [item for item in saved_schedule if str(item["scheduled_date"]) == selected_date]
        completed, total, pct = schedule_completion(day_schedule)
        st.progress(
            pct / 100,
            text=(
                f"Week {selected_day['week_number']} · {selected_day['day_name']} "
                f"completion · {completed}/{total} meals"
            ),
        )
        is_active_day = selected_date == active_date
        is_completed_day = selected_day["status"] == "Completed"
        if not is_active_day and not is_completed_day:
            st.info(
                f"This is a future preview. Complete {day_by_date[active_date]['day_name']} first; "
                "NutriPulse will then move here automatically."
            )
            if st.button("Return to active day", width="stretch"):
                st.session_state.plan_active_date_requested = active_date
                st.rerun()
        render_schedule_rows(
            day_schedule,
            f"plan_{selected_day['week_number']}_{selected_date}",
            interactive=is_active_day or is_completed_day,
        )
    else:
        st.info("Generate a plan to start the automatic day and week schedule.")
    with st.expander("Smart grocery list"):
        groceries = grocery_list(plan)
        columns = st.columns(len(groceries))
        for column, (group, items) in zip(columns, groceries.items()):
            column.markdown(f"**{group}**")
            column.markdown("\n".join(f"- {item}" for item in items))
    st.subheader("Download plan")
    x1, x2, x3 = st.columns(3)
    x1.download_button("Download styled PDF", plan_to_pdf(plan, profile["name"]), "NutriPulse_Diet_Plan.pdf", "application/pdf", type="primary", width="stretch")
    x2.download_button("Download CSV", plan_to_csv(plan), "NutriPulse_Diet_Plan.csv", "text/csv", width="stretch")
    x3.download_button("Download JSON", plan_to_json(plan), "NutriPulse_Diet_Plan.json", "application/json", width="stretch")


def _render_vision_diary_legacy() -> None:
    hero(
        "Built-in Food-101 computer vision",
        "Upload a meal. Let AI suggest.<br><em>You stay in control.</em>",
        "The bundled MobileNetV2 model predicts among 101 dish classes, then links the result to the nutrition database for human confirmation.",
        "Local CPU inference · no API key",
    )
    vision = food_vision_status()
    status_columns = st.columns(4)
    status_columns[0].metric("Vision engine", vision["status"])
    status_columns[1].metric("Recognized dishes", vision.get("classes", 0))
    status_columns[2].metric("Reported top-1", f"{vision.get('reported_top1_accuracy', 0):.1%}" if vision.get("reported_top1_accuracy") else "—")
    status_columns[3].metric("Model integrity", vision.get("integrity", "Unavailable"))
    if vision["status"] == "Ready":
        st.success(vision["message"])
    else:
        st.error(f"{vision['status']}: {vision['message']}")

    left, right = st.columns([1, 1.08])
    with left:
        st.subheader("1 · Analyze meal image")
        image = st.file_uploader("Upload a meal image", type=["png","jpg","jpeg","webp"], key="meal_image")
        if image:
            image_bytes = image.getvalue()
            signature = hashlib.sha256(image_bytes).hexdigest()[:16]
            st.image(image_bytes, caption="Uploaded meal", width="stretch")
            if vision["status"] == "Ready" and st.session_state.vision_signature != signature:
                with st.spinner("Recognizing the dish with MobileNetV2…"):
                    result = predict_food_image(image_bytes)
                st.session_state.vision_predictions = result
                st.session_state.vision_signature = signature
                if result.get("status") == "ready" and result.get("predictions"):
                    st.session_state.food_search = result["predictions"][0]["label"]
            result = st.session_state.get("vision_predictions")
            if result and result.get("status") == "ready":
                top = result["predictions"][0]
                p1, p2, p3 = st.columns(3)
                p1.metric("Top suggestion", top["label"])
                p2.metric("Image confidence", f"{top['confidence']:.1%}")
                p3.metric("Confidence level", result["confidence_level"])
                prediction_frame = pd.DataFrame([
                    {"Suggested dish": row["label"], "Confidence": row["confidence"]}
                    for row in result["predictions"]
                ])
                st.dataframe(
                    prediction_frame,
                    column_config={"Confidence": st.column_config.ProgressColumn("Confidence", min_value=0.0, max_value=1.0, format="percent")},
                    width="stretch", hide_index=True,
                )
                selected_prediction = st.selectbox(
                    "Choose the closest suggestion",
                    [row["label"] for row in result["predictions"]],
                    key="selected_vision_prediction",
                )
                if st.button("Use this suggestion for nutrition matching", type="primary", width="stretch"):
                    st.session_state.food_search = selected_prediction
                    st.rerun()
                if result["confidence_level"] == "Low":
                    st.warning("The image result has low confidence. Try a clearer close-up photo or type the food name manually.")
                st.caption(
                    f"{result['model']} · {result['runtime']} · Food-101 top-1 benchmark 76.3%. "
                    "The model cannot see hidden ingredients, oil, allergens or portion weight."
                )
            elif result and result.get("status") != "ready":
                st.warning(result.get("message", "Vision inference is unavailable."))
            if vision["status"] == "Ready" and st.button("Re-analyze image", width="stretch"):
                st.session_state.vision_signature = None
                st.rerun()
        else:
            st.info("Use a clear, well-lit photo with the main dish centered. JPG, PNG and WebP files up to 10 MB are supported.")
    with right:
        st.subheader("2 · Confirm food and portion")
        database_tab, custom_tab = st.tabs(["Match nutrition database", "Enter a custom dish"])
        with database_tab:
            query = st.text_input(
                "Predicted or known food name", placeholder="e.g., pizza, grilled salmon, lentils",
                key="food_search",
            )
            matches = search_foods_smart(frame, query, limit=40)
            if matches.empty:
                st.warning("No close database record was found. Try fewer words or use the custom-dish tab.")
            else:
                if "match_score" in matches.columns and query:
                    st.caption("Closest records are ranked from the predicted label. Confirm the exact food before logging.")
                options = matches["food_name"].tolist()
                selected_name = st.selectbox("Confirm nutrition record", options, key="vision_database_match")
                servings = st.number_input("Servings", .25, 10.0, 1.0, .25, key="vision_servings")
                meal = st.selectbox("Meal", ["Breakfast","Lunch","Dinner","Snack"], key="vision_meal")
                selected_food = matches[matches["food_name"] == selected_name].iloc[0].to_dict()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Calories", f"{selected_food['calories']*servings:.0f}")
                m2.metric("Protein", f"{selected_food['protein_g']*servings:.1f} g")
                m3.metric("Carbs", f"{selected_food['carbs_g']*servings:.1f} g")
                m4.metric("Fibre", f"{selected_food['fiber_g']*servings:.1f} g")
                prediction = predict_quality(selected_food)
                if prediction["status"] == "ready":
                    st.markdown(f"**Nutrition classifier:** {prediction['title']} · {prediction['confidence']:.0%} confidence")
                else:
                    st.warning(prediction.get("message", "Nutrition classifier unavailable."))
                if st.button("Add confirmed record to diary", type="primary", width="stretch"):
                    add_food_log(active_profile_id, date.today().isoformat(), meal, selected_food, servings)
                    st.success("Confirmed food added to today's diary.")
                    st.rerun()
        with custom_tab:
            with st.form("custom_food_log_form"):
                predicted_default = ""
                current_result = st.session_state.get("vision_predictions")
                if current_result and current_result.get("status") == "ready":
                    predicted_default = current_result["predictions"][0]["label"]
                custom_name = st.text_input("Dish name", predicted_default, key="custom_dish_name")
                ca, cb, cc = st.columns(3)
                custom_calories = ca.number_input("Calories", 0.0, 3000.0, 350.0, 10.0)
                custom_protein = cb.number_input("Protein (g)", 0.0, 250.0, 15.0, 1.0)
                custom_carbs = cc.number_input("Carbs (g)", 0.0, 400.0, 40.0, 1.0)
                cd, ce, cf = st.columns(3)
                custom_fat = cd.number_input("Fat (g)", 0.0, 250.0, 12.0, 1.0)
                custom_fiber = ce.number_input("Fibre (g)", 0.0, 100.0, 5.0, 1.0)
                custom_servings = cf.number_input("Servings", .25, 10.0, 1.0, .25)
                custom_meal = st.selectbox("Meal", ["Breakfast","Lunch","Dinner","Snack"], key="custom_meal")
                custom_submit = st.form_submit_button("Add custom dish to diary", type="primary", width="stretch")
            if custom_submit:
                if not custom_name.strip():
                    st.error("Enter a dish name.")
                else:
                    custom_food = {
                        "food_name": custom_name.strip(), "food_type": "Custom",
                        "calories": custom_calories, "protein_g": custom_protein,
                        "carbs_g": custom_carbs, "fat_g": custom_fat, "fiber_g": custom_fiber,
                        "sugar_g": 0.0, "sodium_mg": 0.0,
                    }
                    add_food_log(active_profile_id, date.today().isoformat(), custom_meal, custom_food, custom_servings)
                    st.success("Custom dish added. Sugar and sodium remain zero because they were not supplied.")
                    st.rerun()
    logs = get_food_logs(active_profile_id, date.today().isoformat())
    if logs:
        st.subheader("Today’s food diary")
        log_frame = pd.DataFrame(logs)
        totals = log_frame[["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]].sum()
        total_columns = st.columns(5)
        for column, label, field, suffix in zip(
            total_columns,
            ["Calories", "Protein", "Carbs", "Fat", "Fibre"],
            ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"],
            [" kcal", " g", " g", " g", " g"],
        ):
            column.metric(label, f"{totals[field]:.1f}{suffix}")
        st.dataframe(log_frame[["meal","food_name","servings","calories","protein_g","carbs_g","fat_g","fiber_g"]], width="stretch", hide_index=True)
        delete_options = {
            f"{row['meal']} · {row['food_name']} · {row['calories']:.0f} kcal": row["id"]
            for row in logs
        }
        with st.expander("Remove an incorrect diary entry"):
            delete_label = st.selectbox("Entry", list(delete_options), key="delete_food_entry")
            if st.button("Remove selected entry", key="delete_food_button"):
                if delete_food_log(delete_options[delete_label], active_profile_id):
                    st.success("Entry removed.")
                    st.rerun()


def _render_food_analysis_summary(analysis: dict) -> None:
    if analysis.get("status") == "needs-confirmation":
        st.warning(analysis.get("message", "Confirm the dish manually."))
        st.caption(analysis.get("estimate_basis", ""))
        return
    if analysis.get("status") != "ready":
        st.error(analysis.get("message", "Food analysis is unavailable."))
        return

    food = analysis["nutrition_match"]
    nutrition = analysis["nutrition"]
    quality = analysis.get("quality") or {}
    label = quality.get("label", "Review")
    verdict = quality.get("title", "Nutrition review required")
    st.markdown(
        f'<section class="np-vision-result"><div class="np-eyebrow">INSTANT NUTRITION INTELLIGENCE</div>'
        f'<h2>{html.escape(str(analysis["selected_label"]))}</h2>'
        f'<p>Closest database match: <strong>{html.escape(str(food.get("food_name", "Unknown")))}</strong></p>'
        f'<div class="np-verdict"><span>{html.escape(str(label))}</span>{html.escape(str(verdict))}</div></section>',
        unsafe_allow_html=True,
    )
    first_row = st.columns(4)
    first_row[0].metric("Energy", f"{nutrition['calories']:.0f} kcal")
    first_row[1].metric("Protein", f"{nutrition['protein_g']:.1f} g")
    first_row[2].metric("Carbohydrate", f"{nutrition['carbs_g']:.1f} g")
    first_row[3].metric("Total fat", f"{nutrition['fat_g']:.1f} g")
    second_row = st.columns(4)
    second_row[0].metric("Fibre", f"{nutrition['fiber_g']:.1f} g")
    second_row[1].metric("Sugar", f"{nutrition['sugar_g']:.1f} g")
    second_row[2].metric("Sodium", f"{nutrition['sodium_mg']:.0f} mg")
    second_row[3].metric("Health rank", f"{analysis['health_score']:.0f}/100")

    positive_column, watch_column = st.columns(2)
    with positive_column:
        st.markdown("#### Positive signals")
        for item in analysis.get("positives", []):
            st.success(item)
    with watch_column:
        st.markdown("#### Watch points")
        watchouts = analysis.get("watchouts") or ["No major threshold flag in the linked database record"]
        for item in watchouts:
            st.warning(item)
    st.caption(analysis["estimate_basis"])
    with st.expander("Important image-analysis limitations"):
        st.markdown("\n".join(f"- {item}" for item in analysis.get("limitations", [])))


def render_vision_diary() -> None:
    hero(
        "NutriLens · Food intelligence",
        "Analyze any meal.<br><em>See beyond the plate.</em>",
        "Upload a food photo or paste a direct public image URL. NutriPulse recognizes the dish, links the closest nutrition record, estimates calories and macros, scores the profile, and activates transparent safety alerts.",
        "Private local inference · public URL safeguards",
        image_path=ASSET_DIR / "food_vision_luxury.jpg",
    )
    vision = food_vision_status()
    status_columns = st.columns(4)
    status_columns[0].metric("Vision engine", vision["status"])
    status_columns[1].metric("Dish classes", vision.get("classes", 0))
    status_columns[2].metric("Benchmark top-1", f"{vision.get('reported_top1_accuracy', 0):.1%}" if vision.get("reported_top1_accuracy") else "—")
    status_columns[3].metric("Integrity", vision.get("integrity", "Unavailable"))
    if vision["status"] != "Ready":
        st.error(f"{vision['status']}: {vision['message']}")

    source_column, result_column = st.columns([0.92, 1.28], gap="large")
    with source_column:
        st.markdown('<div class="np-section-kicker">01 · IMAGE SOURCE</div>', unsafe_allow_html=True)
        source_mode = st.radio(
            "Choose image source", ["Upload from device", "Public image URL"],
            horizontal=True, label_visibility="collapsed", key="vision_source_mode",
        )
        if source_mode == "Upload from device":
            uploaded = st.file_uploader(
                "Upload JPG, PNG or WebP", type=["png", "jpg", "jpeg", "webp"],
                key="meal_image_v32", help="Maximum 10 MB. A clear, centred food image works best.",
            )
            if uploaded:
                incoming = uploaded.getvalue()
                incoming_hash = hashlib.sha256(incoming).hexdigest()
                existing_hash = str(st.session_state.vision_image_source.get("sha256", ""))
                if incoming_hash != existing_hash:
                    st.session_state.vision_image_bytes = incoming
                    st.session_state.vision_image_source = {
                        "kind": "upload", "name": uploaded.name, "sha256": incoming_hash,
                        "size_bytes": len(incoming),
                    }
                    st.session_state.vision_signature = None
                    st.session_state.last_food_analysis = None
                    st.session_state.vision_confirmed_dish_name = ""
        else:
            public_url = st.text_input(
                "Direct image URL", placeholder="https://example.com/meal.jpg",
                key="vision_public_url",
            )
            st.caption("Use a direct JPG, PNG or WebP link. Private/local addresses and files over 10 MB are blocked.")
            if st.button("Securely fetch image", type="primary", width="stretch", key="fetch_public_food_image"):
                try:
                    with st.spinner("Validating and downloading the public image…"):
                        downloaded, metadata = fetch_public_image(public_url)
                    metadata.update({"kind": "url", "sha256": hashlib.sha256(downloaded).hexdigest()})
                    st.session_state.vision_image_bytes = downloaded
                    st.session_state.vision_image_source = metadata
                    st.session_state.vision_signature = None
                    st.session_state.last_food_analysis = None
                    st.session_state.vision_confirmed_dish_name = ""
                    st.rerun()
                except RemoteImageError as exc:
                    st.error(str(exc))

        source = st.session_state.get("vision_image_source") or {}
        expected_kind = "upload" if source_mode == "Upload from device" else "url"
        image_bytes = st.session_state.get("vision_image_bytes") if source.get("kind") == expected_kind else None
        if image_bytes:
            caption = source.get("name") or source.get("domain") or "Selected food image"
            st.image(image_bytes, caption=caption, width="stretch")
            if source.get("kind") == "url":
                st.caption(
                    f"{source.get('width', '—')} × {source.get('height', '—')} px · "
                    f"{float(source.get('size_bytes', 0))/1024:.0f} KB · {source.get('domain', '')}"
                )
            servings = st.number_input(
                "Estimated portions / servings", 0.25, 10.0, 1.0, 0.25,
                key="vision_analysis_servings",
                help="The model cannot measure portion size from a single image. Adjust this manually.",
            )
            analysis_signature = f"{hashlib.sha256(image_bytes).hexdigest()}:{servings:.2f}"
            if vision["status"] == "Ready" and st.session_state.vision_signature != analysis_signature:
                with st.spinner("Recognizing the dish and linking nutrition intelligence…"):
                    try:
                        analysis = analyze_food_image(image_bytes, frame, servings=servings)
                    except (ValueError, OSError) as exc:
                        analysis = {"status": "error", "message": str(exc)}
                st.session_state.last_food_analysis = analysis
                st.session_state.vision_predictions = analysis.get("vision")
                st.session_state.vision_signature = analysis_signature
                if analysis.get("selected_label"):
                    st.session_state.food_search = analysis["selected_label"]
                st.rerun()
            if st.button("Clear current image and alerts", width="stretch", key="clear_food_analysis"):
                st.session_state.vision_image_bytes = None
                st.session_state.vision_image_source = {}
                st.session_state.vision_signature = None
                st.session_state.vision_predictions = None
                st.session_state.last_food_analysis = None
                st.session_state.vision_confirmed_dish_name = ""
                st.rerun()
        else:
            st.info("Choose an image source to begin. Internet search-result pages are not direct image URLs; open the image itself and copy its image address.")

    with result_column:
        st.markdown('<div class="np-section-kicker">02 · AI ANALYSIS</div>', unsafe_allow_html=True)
        analysis = st.session_state.get("last_food_analysis")
        if not analysis:
            st.markdown(
                '<div class="np-empty-vision"><span>◇</span><h3>Nutrition intelligence will appear here</h3>'
                '<p>Dish predictions, confidence, calories, protein, carbohydrates, fat, fibre, sugar, sodium, health classification and safety notices.</p></div>',
                unsafe_allow_html=True,
            )
        else:
            vision_result = analysis.get("vision") or {}
            predictions = vision_result.get("predictions") or []
            if predictions:
                top = predictions[0]
                confidence_columns = st.columns(3)
                confidence_columns[0].metric("Top suggestion", top["label"])
                confidence_columns[1].metric("Confidence", f"{top['confidence']:.1%}")
                confidence_columns[2].metric("Confidence level", vision_result.get("confidence_level", "—"))
                labels = [item["label"] for item in predictions]
                current_label = analysis.get("selected_label", labels[0])
                selected_label = st.selectbox(
                    "Choose the closest model suggestion", labels,
                    index=labels.index(current_label) if current_label in labels else 0,
                    key="vision_selected_label_v32",
                )
                if selected_label != current_label and st.button(
                    "Recalculate using selected dish", type="primary", width="stretch",
                    key="recalculate_selected_dish",
                ):
                    try:
                        updated = analyze_food_image(
                            st.session_state.vision_image_bytes, frame,
                            servings=st.session_state.vision_analysis_servings,
                            selected_label=selected_label,
                        )
                        st.session_state.last_food_analysis = updated
                        st.session_state.food_search = selected_label
                        st.rerun()
                    except (ValueError, OSError) as exc:
                        st.error(str(exc))
                if vision_result.get("confidence_level") == "Low":
                    st.warning("Low-confidence recognition: manually confirm the dish before using the estimate.")
                with st.form("confirm_actual_dish_form"):
                    confirmed_name = st.text_input(
                        "Actual dish name",
                        placeholder="e.g., chicken biryani, daal chawal, beef pulao",
                        key="vision_confirmed_dish_name",
                        help="Use this for regional dishes or any food outside the local model's 101 classes.",
                    )
                    confirm_dish = st.form_submit_button(
                        "Use actual dish name and match nutrition", type="primary", width="stretch",
                    )
                if confirm_dish:
                    if not confirmed_name.strip():
                        st.error("Enter the actual dish name first.")
                    else:
                        try:
                            updated = analyze_food_image(
                                st.session_state.vision_image_bytes, frame,
                                servings=st.session_state.vision_analysis_servings,
                                selected_label=confirmed_name.strip(),
                            )
                            st.session_state.last_food_analysis = updated
                            st.session_state.food_search = confirmed_name.strip()
                            st.rerun()
                        except (ValueError, OSError) as exc:
                            st.error(str(exc))
            _render_food_analysis_summary(analysis)
            if profile.get("allergies"):
                st.error("Allergy alert: an image cannot verify ingredients or cross-contact. Confirm the recipe and preparation process.")

    st.markdown('<div class="np-section-kicker">03 · CONFIRM, REFINE & LOG</div>', unsafe_allow_html=True)
    database_tab, custom_tab = st.tabs(["Confirm nutrition database record", "Enter a custom dish"])
    with database_tab:
        query = st.text_input(
            "Predicted or known food name", placeholder="e.g., pizza, grilled salmon, lentils",
            key="food_search",
        )
        matches = search_foods_smart(frame, query, limit=40)
        if matches.empty:
            st.warning("No close database record was found. Try fewer words or use the custom-dish tab.")
        else:
            controls = st.columns([2, 0.7, 0.9])
            selected_name = controls[0].selectbox("Confirm exact food record", matches["food_name"].tolist(), key="vision_database_match_v32")
            servings = controls[1].number_input("Servings", .25, 10.0, 1.0, .25, key="vision_log_servings")
            meal = controls[2].selectbox("Meal", ["Breakfast", "Lunch", "Dinner", "Snack"], key="vision_log_meal")
            selected_food = matches[matches["food_name"] == selected_name].iloc[0].to_dict()
            metrics = st.columns(7)
            for column, label, field, suffix in zip(
                metrics,
                ["Calories", "Protein", "Carbs", "Fat", "Fibre", "Sugar", "Sodium"],
                ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"],
                [" kcal", " g", " g", " g", " g", " g", " mg"],
            ):
                column.metric(label, f"{float(selected_food[field])*servings:.1f}{suffix}")
            prediction = predict_quality(selected_food)
            if prediction.get("status") == "ready":
                render_quality_result(prediction, selected_name, selected_food)
            if st.button("Add confirmed food to today’s diary", type="primary", width="stretch", key="add_confirmed_vision_food"):
                add_food_log(active_profile_id, date.today().isoformat(), meal, selected_food, servings)
                st.success("Confirmed food added to today’s diary.")
                st.rerun()
    with custom_tab:
        with st.form("custom_food_log_form_v32"):
            current_analysis = st.session_state.get("last_food_analysis") or {}
            custom_name = st.text_input("Dish name", str(current_analysis.get("selected_label", "")))
            row_one = st.columns(4)
            custom_calories = row_one[0].number_input("Calories", 0.0, 3000.0, 350.0, 10.0)
            custom_protein = row_one[1].number_input("Protein (g)", 0.0, 250.0, 15.0, 1.0)
            custom_carbs = row_one[2].number_input("Carbs (g)", 0.0, 400.0, 40.0, 1.0)
            custom_fat = row_one[3].number_input("Fat (g)", 0.0, 250.0, 12.0, 1.0)
            row_two = st.columns(4)
            custom_fiber = row_two[0].number_input("Fibre (g)", 0.0, 100.0, 5.0, 1.0)
            custom_sugar = row_two[1].number_input("Sugar (g)", 0.0, 300.0, 0.0, 1.0)
            custom_sodium = row_two[2].number_input("Sodium (mg)", 0.0, 10000.0, 0.0, 25.0)
            custom_servings = row_two[3].number_input("Servings", .25, 10.0, 1.0, .25)
            custom_meal = st.selectbox("Meal", ["Breakfast", "Lunch", "Dinner", "Snack"], key="custom_meal_v32")
            custom_submit = st.form_submit_button("Add custom dish to diary", type="primary", width="stretch")
        if custom_submit:
            if not custom_name.strip():
                st.error("Enter a dish name.")
            else:
                custom_food = {
                    "food_name": custom_name.strip(), "food_type": "Custom",
                    "calories": custom_calories, "protein_g": custom_protein,
                    "carbs_g": custom_carbs, "fat_g": custom_fat, "fiber_g": custom_fiber,
                    "sugar_g": custom_sugar, "sodium_mg": custom_sodium,
                }
                add_food_log(active_profile_id, date.today().isoformat(), custom_meal, custom_food, custom_servings)
                st.success("Custom dish added to today’s diary.")
                st.rerun()

    logs = get_food_logs(active_profile_id, date.today().isoformat())
    if logs:
        st.subheader("Today’s food diary")
        log_frame = pd.DataFrame(logs)
        totals = log_frame[["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]].sum()
        total_columns = st.columns(5)
        for column, label, field, suffix in zip(
            total_columns,
            ["Calories", "Protein", "Carbs", "Fat", "Fibre"],
            ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"],
            [" kcal", " g", " g", " g", " g"],
        ):
            column.metric(label, f"{totals[field]:.1f}{suffix}")
        st.dataframe(log_frame[["meal", "food_name", "servings", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]], width="stretch", hide_index=True)
        delete_options = {
            f"{row['meal']} · {row['food_name']} · {row['calories']:.0f} kcal": row["id"]
            for row in logs
        }
        with st.expander("Remove an incorrect diary entry"):
            delete_label = st.selectbox("Entry", list(delete_options), key="delete_food_entry_v32")
            if st.button("Remove selected entry", key="delete_food_button_v32"):
                if delete_food_log(delete_options[delete_label], active_profile_id):
                    st.success("Entry removed.")
                    st.rerun()


def render_food_library() -> None:
    manifest_path = DATA_DIR / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    audit = manifest.get("source_audit", {})
    hero(
        "Unified food intelligence",
        f"{audit.get('raw_source_records', len(frame)):,} source rows.<br><em>{len(frame):,} nutrition-ready unique foods.</em>",
        "Search the validated nutrition index, or open the complete source registry to trace food, product, safety and benchmark rows.",
    )
    st.info(
        f"The nine datasets contain {audit.get('raw_source_records', len(frame)):,} raw rows. "
        f"{audit.get('food_related_source_records', len(frame)):,} are food/product related; "
        f"{len(frame):,} unique records have sufficient validated nutrients for comparison and classification."
    )
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    query = c1.text_input("Search", placeholder="Food, ingredient or product")
    categories = ["All"] + sorted(frame["food_type"].unique().tolist())
    category = c2.selectbox("Category", categories)
    max_calories = c3.number_input("Maximum kcal", 0, 3000, 1000)
    min_protein = c4.number_input("Minimum protein", 0.0, 100.0, 0.0)
    result = search_foods(frame, query, category, max_calories if max_calories else None, min_protein, limit=200)
    st.caption(f"{len(result):,} highest-ranked matching records displayed")
    columns = st.columns(4)
    for index, (_, food) in enumerate(result.head(12).iterrows()):
        with columns[index % 4]:
            st.markdown(
                f'<div class="np-food-card"><span class="type">{html.escape(str(food["food_type"]))}</span><h4>{html.escape(str(food["food_name"]))}</h4><span class="kcal">{food["calories"]:.0f} kcal</span><div class="macros">Protein {food["protein_g"]:.1f}g · Fibre {food["fiber_g"]:.1f}g<br>Sugar {food["sugar_g"]:.1f}g · Sodium {food["sodium_mg"]:.0f}mg<br>Health rank {food["healthy_rank_score"]:.0f}/100</div></div>',
                unsafe_allow_html=True,
            )
    st.dataframe(result[["food_id","food_name","food_type","calories","protein_g","carbs_g","fat_g","fiber_g","sugar_g","sodium_mg","healthy_rank_score"]], width="stretch", hide_index=True, height=420)
    registry_path = DATA_DIR / "source_record_registry.csv"
    if registry_path.exists():
        with st.expander("Search every food/product source row — including records without complete macros"):
            registry = pd.read_csv(registry_path, low_memory=False)
            registry = registry[registry["record_type"] != "Person benchmark"]
            source_query = st.text_input("Source registry search", key="food_source_registry_search")
            if source_query.strip():
                registry = registry[
                    registry["record_name"].fillna("").str.contains(source_query.strip(), case=False, regex=False)
                ]
            st.caption(f"{len(registry):,} matching food/product source rows; first 500 displayed.")
            st.dataframe(registry.head(500), width="stretch", hide_index=True, height=420)


def render_progress() -> None:
    hero("Longitudinal monitoring", "Progress that shows<br><em>the pattern, not just the number.</em>", "Track weight, waist, hydration and plan adherence over time with data stored locally in SQLite.")
    with st.form("measurement_form"):
        c1, c2, c3, c4, c5 = st.columns(5)
        measured_on = c1.date_input("Date", date.today())
        weight = c2.number_input("Weight (kg)", 30.0, 300.0, float(profile["weight_kg"]), .1)
        waist = c3.number_input("Waist (cm)", 0.0, 250.0, 0.0, .5)
        water = c4.number_input("Water (L)", 0.0, 10.0, 2.0, .1)
        adherence = c5.slider("Adherence %", 0, 100, 80)
        if st.form_submit_button("Save measurement", type="primary", width="stretch"):
            add_measurement(active_profile_id, measured_on.isoformat(), weight, waist or None, water, adherence)
            st.success("Measurement saved.")
    schedule = list_meal_schedule(active_profile_id)
    if schedule:
        plans = list_plans(active_profile_id)
        plan_names = {str(item["id"]): str(item["name"]) for item in plans}
        daily, weekly = schedule_analytics(schedule, plan_names)
        current_progress = get_schedule_progress(active_profile_id, st.session_state.plan_id)
        metric_columns = st.columns(4)
        metric_columns[0].metric("Completed weeks", int((weekly["status"] == "Completed").sum()))
        metric_columns[1].metric("Active week", f"Week {current_progress.get('active_week_number', 1)}")
        metric_columns[2].metric(
            "All scheduled meals",
            f"{int(weekly['completed'].sum())}/{int(weekly['total'].sum())}",
            f"{(weekly['completed'].sum() / weekly['total'].sum() * 100 if weekly['total'].sum() else 0):.0f}%",
        )
        metric_columns[3].metric("Skipped", int(weekly["skipped"].sum()), "Review barriers")
        left, right = st.columns(2)
        with left:
            fig = px.bar(
                daily, x="day_label", y="completion_pct", color="status",
                title="Daily schedule completion",
                color_discrete_map={"Completed": "#b9f06a", "In progress": "#5ce0d0", "Upcoming": "#6b7280"},
            )
            fig.update_yaxes(range=[0, 100], ticksuffix="%", title="Completion")
            fig.update_xaxes(title=None, type="category")
            st.plotly_chart(plot_layout(fig, 350), width="stretch", config={"displayModeBar": False})
        with right:
            fig = px.line(
                weekly, x="week_label", y="completion_pct", markers=True,
                title="Week-by-week progress", color_discrete_sequence=["#b9f06a"],
            )
            fig.update_yaxes(range=[0, 100], ticksuffix="%", title="Completion")
            fig.update_xaxes(title=None, type="category")
            st.plotly_chart(plot_layout(fig, 350), width="stretch", config={"displayModeBar": False})
        st.subheader("Week completion history")
        week_history = weekly[[
            "plan_name", "week_number", "week_start", "week_end", "completed", "total",
            "completion_pct", "skipped", "status",
        ]].copy()
        week_history.columns = [
            "Plan", "Week", "Start", "End", "Meals completed", "Meals scheduled",
            "Completion %", "Skipped", "Status",
        ]
        st.dataframe(week_history, width="stretch", hide_index=True)
    else:
        st.info("Generate a diet plan to begin automatic daily and weekly progress tracking.")
    measurements = get_measurements(active_profile_id)
    if not measurements:
        st.info("Add your first measurement to start longitudinal charts.")
        return
    data = pd.DataFrame(measurements)
    data["measured_on"] = pd.to_datetime(data["measured_on"])
    c1, c2 = st.columns(2)
    with c1:
        fig = px.line(data, x="measured_on", y="weight_kg", markers=True, title="Weight trend", color_discrete_sequence=["#b9f06a"])
        frame_date_axis(fig, data["measured_on"])
        st.plotly_chart(plot_layout(fig), width="stretch", config={"displayModeBar":False})
    with c2:
        fig = px.bar(data, x="measured_on", y="adherence_pct", title="Plan adherence", color_discrete_sequence=["#5ce0d0"])
        fig.update_yaxes(range=[0,100])
        if len(data) == 1:
            fig.update_traces(width=36 * 60 * 60 * 1000)
        frame_date_axis(fig, data["measured_on"])
        st.plotly_chart(plot_layout(fig), width="stretch", config={"displayModeBar":False})
    st.dataframe(data, width="stretch", hide_index=True)


def render_clinician() -> None:
    if current_user["role"] != "Dietitian":
        st.error("The Clinical Hub is restricted to registered Dietitian accounts.")
        return
    hero(
        "Dietitian-only clinical command center",
        "One private portal.<br><em>Every customer signal in context.</em>",
        "Review profiles, plans, alerts and progress; issue structured questionnaires; and maintain a consent-linked clinical message thread.",
        "Role-gated · customer portal cannot open this workspace",
    )
    customers = list_linked_customers(str(current_user["id"]))
    available_customers = [
        item for item in list_users("Customer")
        if str(item["id"]) not in {str(linked["id"]) for linked in customers}
    ]
    if available_customers:
        with st.expander("Connect another registered customer"):
            choices = {f"{item['display_name']} · @{item['username']}": item["id"] for item in available_customers}
            selected = st.selectbox("Customer account", list(choices), key="dietitian_link_customer")
            if st.button("Add to clinical panel", type="primary", key="link_customer_button"):
                link_dietitian_customer(str(current_user["id"]), str(choices[selected]))
                st.success("Customer linked to your clinical panel.")
                st.rerun()
    if not customers:
        st.info("No customers are connected yet. Ask the customer to connect from Care Team, or add a registered customer above.")
        return

    selected_profile = load_profile(active_profile_id)
    if not selected_profile:
        st.warning("The selected customer has not completed a profile yet.")
        return
    selected_plans = list_plans(active_profile_id)
    selected_alerts = list_alerts(active_profile_id, include_resolved=True)
    selected_measurements = get_measurements(active_profile_id)
    week_start = date.today() - timedelta(days=date.today().weekday())
    selected_schedule = list_meal_schedule(
        active_profile_id, date_from=week_start.isoformat(),
        date_to=(week_start + timedelta(days=6)).isoformat(),
    )
    completed, total, completion_pct = schedule_completion(selected_schedule)
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Customer", selected_profile["name"])
    s2.metric("Active alerts", sum(item["status"] == "Active" for item in selected_alerts))
    s3.metric("Saved plans", len(selected_plans))
    s4.metric("Meal completion", f"{completion_pct:.0f}%", f"{completed}/{total}")
    s5.metric("Progress records", len(selected_measurements))

    overview_tab, questionnaire_tab, messages_tab, reviews_tab = st.tabs([
        "Clinical overview", "Questionnaires", "Secure messages", "Plan review queue",
    ])
    with overview_tab:
        left, right = st.columns([1, 1])
        with left:
            st.subheader("Profile and risk context")
            st.json({
                "age": selected_profile["age"], "biological_sex": selected_profile["biological_sex"],
                "height_cm": selected_profile["height_cm"], "weight_kg": selected_profile["weight_kg"],
                "goal": selected_profile["goal"], "conditions": selected_profile.get("conditions", []),
                "allergies": selected_profile.get("allergies", []),
                "medications_for_review": selected_profile.get("medications", ""),
            }, expanded=True)
        with right:
            st.subheader("Priority alert feed")
            active = [item for item in selected_alerts if item["status"] == "Active"]
            if active:
                for item in active[:6]:
                    alert_card(item, compact=True)
            else:
                st.success("No active alerts for this customer.")
        if selected_measurements:
            measurement_frame = pd.DataFrame(selected_measurements)
            measurement_frame["measured_on"] = pd.to_datetime(measurement_frame["measured_on"])
            fig = px.line(
                measurement_frame, x="measured_on", y="weight_kg", markers=True,
                title="Customer weight history", color_discrete_sequence=["#b9f06a"],
            )
            st.plotly_chart(plot_layout(fig, 290), width="stretch", config={"displayModeBar": False})
    with questionnaire_tab:
        with st.form("dietitian_questionnaire_form"):
            title = st.text_input("Questionnaire title", "Nutrition intake and adherence review")
            questions_text = st.text_area(
                "Questions — one per line",
                "What makes the current plan difficult to follow?\nHave you had any new symptoms or medication changes?\nWhich meals do you most often miss?\nWhat foods would you like included or replaced?",
                height=150,
            )
            if st.form_submit_button("Send questionnaire to customer", type="primary", width="stretch"):
                try:
                    create_questionnaire(
                        str(current_user["id"]), active_profile_id, title,
                        [line.strip() for line in questions_text.splitlines() if line.strip()],
                    )
                    st.success("Questionnaire sent to the customer portal.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        questionnaires = list_questionnaires(
            customer_id=active_profile_id, dietitian_id=str(current_user["id"]),
        )
        for questionnaire in questionnaires:
            with st.expander(f"{questionnaire['status']} · {questionnaire['title']} · {questionnaire['created_at'][:10]}"):
                if questionnaire.get("answers"):
                    for question, answer in questionnaire["answers"].items():
                        st.markdown(f"**{question}**")
                        st.write(answer)
                else:
                    st.caption("Waiting for customer answers.")
    with messages_tab:
        with st.form("dietitian_message_form"):
            subject = st.text_input("Subject", "Plan follow-up")
            body = st.text_area("Message", "Please review the questionnaire and update your meal completion records before our next check-in.")
            if st.form_submit_button("Send secure message", type="primary", width="stretch"):
                try:
                    send_clinical_message(str(current_user["id"]), active_profile_id, subject, body)
                    st.success("Message delivered inside the customer portal.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        for message in list_clinical_messages(str(current_user["id"]), active_profile_id):
            st.markdown(
                f'<div class="np-message"><span>{html.escape(message["sender_name"])} → {html.escape(message["recipient_name"])}</span>'
                f'<h4>{html.escape(message["subject"])}</h4><p>{html.escape(message["body"])}</p>'
                f'<small>{html.escape(message["created_at"][:16].replace("T", " "))} UTC</small></div>',
                unsafe_allow_html=True,
            )
    with reviews_tab:
        if selected_plans:
            plan_options = {f"{item['name']} · {item['created_at'][:10]}": item["id"] for item in selected_plans}
            with st.form("review_form"):
                selected_label = st.selectbox("Plan", list(plan_options))
                note = st.text_area("Clinical note", "Review laboratory-linked constraints, portions and the customer’s recent adherence trend.")
                if st.form_submit_button("Add review request", type="primary", width="stretch"):
                    request_review(plan_options[selected_label], str(current_user["display_name"]), note)
                    st.success("Review request recorded.")
        reviews = list_reviews(active_profile_id)
        if reviews:
            st.dataframe(pd.DataFrame(reviews)[["plan_name", "reviewer", "status", "note", "updated_at"]], width="stretch", hide_index=True)


def clinical_customer_context() -> tuple[dict, list[dict]] | None:
    if current_user["role"] != "Dietitian":
        st.error("This workspace is restricted to approved Dietitian and Administrator accounts.")
        return None
    if not linked_customers:
        message = (
            "No Customer accounts exist yet."
            if is_admin else
            "No customers are assigned to your caseload. Ask the Administrator to create an assignment."
        )
        st.info(message)
        return None
    selected_profile = load_profile(active_profile_id)
    if not selected_profile:
        st.warning("The selected customer has not completed a profile yet.")
        return None
    return selected_profile, list_plans(active_profile_id)


def render_clinical_dashboard() -> None:
    hero(
        "Dietitian Clinical Portal",
        "Your caseload.<br><em>Only clinical work, clearly separated.</em>",
        "Review assigned customers, priority alerts, adherence, plans and follow-up activity from one professional dashboard.",
        "Administrator override active" if is_admin else "Assigned caseload only",
    )
    if not linked_customers:
        clinical_customer_context()
        return
    rows = []
    for customer in linked_customers:
        customer_id = str(customer["id"])
        patient = load_profile(customer_id)
        measurements = get_measurements(customer_id)
        plans = list_plans(customer_id)
        alerts = list_alerts(customer_id, include_resolved=False)
        schedule = list_meal_schedule(customer_id)
        completed, total, completion_pct = schedule_completion(schedule)
        bmi = calculate_bmi(patient["weight_kg"], patient["height_cm"])[0] if patient else None
        rows.append({
            "Customer": customer["display_name"],
            "Age": patient.get("age") if patient else None,
            "Goal": patient.get("goal") if patient else "Profile incomplete",
            "Weight kg": patient.get("weight_kg") if patient else None,
            "BMI": bmi,
            "Active alerts": len([item for item in alerts if item["status"] == "Active"]),
            "Plans": len(plans),
            "Meal adherence %": completion_pct if total else (measurements[-1].get("adherence_pct") if measurements else 0),
            "Last progress": measurements[-1]["measured_on"] if measurements else "No record",
        })
    caseload = pd.DataFrame(rows)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Customers", len(caseload))
    m2.metric("Active alerts", int(caseload["Active alerts"].sum()))
    m3.metric("Plans reviewed", sum(len(list_reviews(str(item["id"]))) for item in linked_customers))
    m4.metric("Average adherence", f"{caseload['Meal adherence %'].fillna(0).mean():.0f}%")
    st.dataframe(caseload, width="stretch", hide_index=True)
    st.caption("Use the Active customer selector in the sidebar, then open a clinical workspace for detailed review.")


def render_clinical_overview() -> None:
    context = clinical_customer_context()
    if not context:
        return
    selected_profile, selected_plans = context
    hero(
        "Customer clinical overview",
        f"{html.escape(str(selected_profile['name']))}.<br><em>Risks, vitals and progress in context.</em>",
        "The selected customer is available because of an active caseload assignment or Administrator override.",
    )
    bmi, bmi_label = calculate_bmi(selected_profile["weight_kg"], selected_profile["height_cm"])
    measurements = get_measurements(active_profile_id)
    alerts = list_alerts(active_profile_id, include_resolved=False)
    food_logs = get_food_logs(active_profile_id)
    cards = st.columns(6)
    cards[0].metric("Age", selected_profile["age"])
    cards[1].metric("Goal", selected_profile["goal"])
    cards[2].metric("Weight", f"{selected_profile['weight_kg']:.1f} kg")
    cards[3].metric("BMI", f"{bmi:.1f}", bmi_label)
    cards[4].metric("Plans", len(selected_plans))
    cards[5].metric("Diary entries", len(food_logs))
    left, right = st.columns(2)
    with left:
        st.subheader("Flagged conditions")
        conditions = selected_profile.get("conditions", [])
        st.warning(" · ".join(conditions)) if conditions else st.success("No conditions recorded.")
        st.subheader("Allergies")
        allergies = selected_profile.get("allergies", [])
        st.error(" · ".join(allergies)) if allergies else st.success("No allergies recorded.")
        if selected_profile.get("medications"):
            st.info(f"Medication list for review: {selected_profile['medications']}")
    with right:
        st.subheader("Priority alerts")
        active = [item for item in alerts if item["status"] == "Active"]
        if active:
            for item in active[:6]:
                alert_card(item, compact=True)
        else:
            st.success("No active alerts.")
    if measurements:
        data = pd.DataFrame(measurements)
        data["measured_on"] = pd.to_datetime(data["measured_on"])
        c1, c2 = st.columns(2)
        with c1:
            fig = px.line(data, x="measured_on", y="weight_kg", markers=True, title="Weight trend", color_discrete_sequence=["#b9f06a"])
            frame_date_axis(fig, data["measured_on"])
            st.plotly_chart(plot_layout(fig), width="stretch", config={"displayModeBar": False})
        with c2:
            fig = px.line(data, x="measured_on", y="adherence_pct", markers=True, title="Adherence trend", color_discrete_sequence=["#5ce0d0"])
            fig.update_yaxes(range=[0, 100], ticksuffix="%")
            frame_date_axis(fig, data["measured_on"])
            st.plotly_chart(plot_layout(fig), width="stretch", config={"displayModeBar": False})


def render_clinical_diary() -> None:
    context = clinical_customer_context()
    if not context:
        return
    selected_profile, _ = context
    hero(
        "Food diary review",
        f"Everything {html.escape(str(selected_profile['name']))} recorded.<br><em>Daily intake, clearly totalled.</em>",
        "Review meal, serving, calorie and macro records without exposing Dietitian-only notes.",
    )
    logs = get_food_logs(active_profile_id)
    if not logs:
        st.info("This customer has not recorded food yet.")
        return
    data = pd.DataFrame(logs)
    data["log_date"] = pd.to_datetime(data["log_date"])
    daily = data.groupby("log_date", as_index=False)[["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]].sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Diary entries", len(data))
    m2.metric("Recorded days", data["log_date"].nunique())
    m3.metric("Average calories/day", f"{daily['calories'].mean():.0f}")
    m4.metric("Average protein/day", f"{daily['protein_g'].mean():.1f} g")
    fig = px.bar(daily, x="log_date", y="calories", title="Daily calorie totals", color_discrete_sequence=["#5ce0d0"])
    frame_date_axis(fig, daily["log_date"])
    st.plotly_chart(plot_layout(fig, 320), width="stretch", config={"displayModeBar": False})
    display_columns = ["log_date", "meal", "food_name", "servings", "calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]
    st.dataframe(data[display_columns].sort_values("log_date", ascending=False), width="stretch", hide_index=True)


def render_clinical_plans() -> None:
    context = clinical_customer_context()
    if not context:
        return
    selected_profile, plans = context
    hero(
        "Diet plan oversight",
        "Analyze reports. Generate a plan.<br><em>Record the professional review.</em>",
        "View customer-generated plans, create a clinical draft, and log a formal review with the acting professional role.",
    )
    reports = list_lab_reports(active_profile_id)
    report_values = reports[0]["values"] if reports else []
    safety = assess_safety(report_values, selected_profile) if report_values else {"can_generate": True, "level": "wellness", "reasons": []}
    c1, c2 = st.columns([1, 1])
    with c1:
        st.metric("Available plans", len(plans))
        st.caption(f"Latest verified report: {reports[0]['created_at'][:10]}" if reports else "No linked report; wellness constraints only")
    with c2:
        if st.button("Generate Dietitian plan for selected customer", type="primary", disabled=not safety.get("can_generate", True), width="stretch"):
            try:
                plan = generate_plan(selected_profile, report_values)
                plan_id = save_plan(active_profile_id, plan, reports[0]["id"] if reports else None)
                week_start = date.today() - timedelta(days=date.today().weekday())
                create_meal_schedule(active_profile_id, plan_id, plan, week_start.isoformat())
                request_review(
                    plan_id, str(current_user["display_name"]),
                    "Dietitian-generated clinical draft created after profile and report review.",
                    reviewer_role="Dietitian", status="Generated",
                )
                st.success("Dietitian plan generated, scheduled and added to the formal review history.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if not safety.get("can_generate", True):
        st.error("Automatic plan generation is blocked: " + "; ".join(safety.get("reasons", [])))
    plans = list_plans(active_profile_id)
    if not plans:
        st.info("No plans are available for this customer.")
        return
    options = {f"{item['name']} · {item['created_at'][:10]} · {item['calories']} kcal": item for item in plans}
    selected_label = st.selectbox("Select plan", list(options))
    selected = options[selected_label]
    p1, p2, p3 = st.columns(3)
    p1.metric("Target calories", f"{selected['calories']} kcal")
    p2.metric("Plan status", selected["status"])
    p3.metric("Days", len(selected["plan"].get("days", [])))
    with st.expander("View full seven-day plan", expanded=True):
        for day in selected["plan"].get("days", []):
            st.markdown(f"**{day.get('day', 'Day')}**")
            st.write(" · ".join(f"{meal.get('time', '')} {meal.get('name', '')}" for meal in day.get("meals", [])))
    with st.form("formal_plan_review"):
        acting_role = st.selectbox("Acting role", ["Dietitian", "Doctor", "Renal Dietitian", "Diabetes Educator"])
        review_status = st.selectbox("Review status", ["Approved", "Changes requested", "Reviewed", "Escalated"])
        review_note = st.text_area("Formal review note")
        submit_review = st.form_submit_button("Save formal clinical review", type="primary", width="stretch")
    if submit_review:
        if len(review_note.strip()) < 3:
            st.error("Add a review note.")
        else:
            request_review(
                str(selected["id"]), str(current_user["display_name"]), review_note,
                reviewer_role=acting_role, status=review_status,
            )
            st.success("Formal review saved.")
            st.rerun()
    history = list_reviews(active_profile_id)
    if history:
        columns = ["plan_name", "reviewer", "reviewer_role", "status", "note", "updated_at"]
        st.dataframe(pd.DataFrame(history)[columns], width="stretch", hide_index=True)


def render_clinical_reports() -> None:
    context = clinical_customer_context()
    if not context:
        return
    reports = list_lab_reports(active_profile_id)
    if reports:
        st.subheader("Saved report history")
        summary = pd.DataFrame([{
            "Report": item["file_name"], "Safety level": item["safety_level"],
            "Verified values": len(item["values"]), "Reviewed by": item.get("reviewed_by", ""),
            "Timestamp": item["created_at"],
        } for item in reports])
        st.dataframe(summary, width="stretch", hide_index=True)
    render_labs(clinical_mode=True)


def render_clinical_progress() -> None:
    context = clinical_customer_context()
    if not context:
        return
    selected_profile, _ = context
    hero(
        "Clinical progress analytics",
        f"{html.escape(str(selected_profile['name']))}.<br><em>Weight, adherence and daily completion.</em>",
        "Read-only clinical monitoring across registered progress records and scheduled-plan completion.",
    )
    measurements = get_measurements(active_profile_id)
    schedule = list_meal_schedule(active_profile_id)
    if schedule:
        plans = list_plans(active_profile_id)
        plan_names = {str(item["id"]): str(item["name"]) for item in plans}
        daily, weekly = schedule_analytics(schedule, plan_names)
        latest_plan_id = str(plans[0]["id"]) if plans else None
        progress = get_schedule_progress(active_profile_id, latest_plan_id)
        metrics = st.columns(4)
        metrics[0].metric("Completed weeks", int((weekly["status"] == "Completed").sum()))
        metrics[1].metric("Current cycle", f"Week {progress.get('active_week_number', 1)}")
        metrics[2].metric("Meals completed", f"{int(weekly['completed'].sum())}/{int(weekly['total'].sum())}")
        metrics[3].metric("Skipped", int(weekly["skipped"].sum()), "Follow-up signal")
        left, right = st.columns(2)
        with left:
            fig = px.bar(
                daily, x="day_label", y="completion_pct", color="status",
                title="Daily plan completion",
                color_discrete_map={"Completed": "#b9f06a", "In progress": "#5ce0d0", "Upcoming": "#6b7280"},
            )
            fig.update_yaxes(range=[0, 100], ticksuffix="%")
            fig.update_xaxes(title=None, type="category")
            st.plotly_chart(plot_layout(fig, 330), width="stretch", config={"displayModeBar": False})
        with right:
            fig = px.line(
                weekly, x="week_label", y="completion_pct", markers=True,
                title="Weekly completion trajectory", color_discrete_sequence=["#b9f06a"],
            )
            fig.update_yaxes(range=[0, 100], ticksuffix="%")
            fig.update_xaxes(title=None, type="category")
            st.plotly_chart(plot_layout(fig, 330), width="stretch", config={"displayModeBar": False})
        with st.expander("Week-by-week clinical audit", expanded=True):
            st.dataframe(
                weekly[["plan_name", "week_number", "week_start", "week_end", "completed", "total", "completion_pct", "skipped", "status"]],
                width="stretch", hide_index=True,
            )
    if not measurements:
        st.info("No weight or adherence measurements have been recorded.")
        return
    data = pd.DataFrame(measurements)
    data["measured_on"] = pd.to_datetime(data["measured_on"])
    c1, c2 = st.columns(2)
    with c1:
        fig = px.line(data, x="measured_on", y="weight_kg", markers=True, title="Weight trend", color_discrete_sequence=["#b9f06a"])
        frame_date_axis(fig, data["measured_on"])
        st.plotly_chart(plot_layout(fig), width="stretch", config={"displayModeBar": False})
    with c2:
        fig = px.line(data, x="measured_on", y="adherence_pct", markers=True, title="Adherence trend", color_discrete_sequence=["#5ce0d0"])
        fig.update_yaxes(range=[0, 100], ticksuffix="%")
        frame_date_axis(fig, data["measured_on"])
        st.plotly_chart(plot_layout(fig), width="stretch", config={"displayModeBar": False})
    st.dataframe(data, width="stretch", hide_index=True)


def render_clinical_notes_and_prescriptions() -> None:
    context = clinical_customer_context()
    if not context:
        return
    selected_profile, _ = context
    hero(
        "Clinical notes and nutrition prescriptions",
        "Private reasoning.<br><em>Clear customer-facing action.</em>",
        "Notes remain permanently hidden from customers. Nutrition prescriptions appear in the customer Care Team workspace.",
    )
    notes_tab, prescriptions_tab = st.tabs(["Private clinical notes", "Nutrition prescriptions"])
    with notes_tab:
        with st.form("private_clinical_note"):
            note = st.text_area("Dietitian-only note", placeholder="Assessment, barriers, interpretation and follow-up reasoning…")
            save_note = st.form_submit_button("Save private note", type="primary", width="stretch")
        if save_note:
            try:
                add_clinical_note(str(current_user["id"]), active_profile_id, note)
                st.success("Private note saved. It is not visible in the customer portal.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        for item in list_clinical_notes(active_profile_id):
            st.markdown(
                f'<div class="np-message"><span>PRIVATE · {html.escape(item["dietitian_name"])}</span>'
                f'<p>{html.escape(item["note"])}</p><small>{html.escape(item["created_at"])}</small></div>',
                unsafe_allow_html=True,
            )
    with prescriptions_tab:
        st.info("Use this for nutrition care within professional scope. Medication prescribing and diagnosis are outside this prototype.")
        with st.form("clinical_prescription"):
            category = st.selectbox("Category", ["Meal plan", "Nutrition target", "Supplement recommendation", "Food restriction", "Monitoring", "Referral / follow-up"])
            title = st.text_input("Prescription title")
            instructions = st.text_area("Customer instructions")
            prescribe = st.form_submit_button("Issue nutrition prescription", type="primary", width="stretch")
        if prescribe:
            try:
                add_clinical_prescription(str(current_user["id"]), active_profile_id, category, title, instructions)
                st.success("Nutrition prescription issued to the customer portal.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        prescriptions = list_clinical_prescriptions(active_profile_id)
        if prescriptions:
            st.dataframe(pd.DataFrame(prescriptions)[["category", "title", "instructions", "status", "dietitian_name", "created_at"]], width="stretch", hide_index=True)


def render_clinical_messages() -> None:
    context = clinical_customer_context()
    if not context:
        return
    selected_profile, _ = context
    hero(
        "Questions and recommendations",
        f"A complete care thread with {html.escape(str(selected_profile['name']))}.<br><em>Open questions close on reply.</em>",
        "Send a Question or Recommendation, review the complete conversation, and issue structured questionnaires when detail is needed.",
    )
    messages_tab, questionnaire_tab = st.tabs(["Conversation", "Structured questionnaires"])
    with messages_tab:
        with st.form("typed_clinical_message"):
            message_type = st.selectbox("Message type", ["Question", "Recommendation"])
            subject = st.text_input("Subject")
            body = st.text_area("Message")
            send = st.form_submit_button("Send to customer", type="primary", width="stretch")
        if send:
            try:
                send_clinical_message(
                    str(current_user["id"]), active_profile_id, subject, body,
                    message_type=message_type,
                )
                st.success(f"{message_type} sent.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        for message in list_clinical_messages(str(current_user["id"]), active_profile_id):
            st.markdown(
                f'<div class="np-message"><span>{html.escape(message.get("message_type", "Message"))} · '
                f'{html.escape(message["sender_name"])} → {html.escape(message["recipient_name"])} · '
                f'{html.escape(message.get("status", ""))}</span><h4>{html.escape(message["subject"])}</h4>'
                f'<p>{html.escape(message["body"])}</p><small>{html.escape(message["created_at"])}</small></div>',
                unsafe_allow_html=True,
            )
    with questionnaire_tab:
        with st.form("clinical_questionnaire_form_v41"):
            title = st.text_input("Questionnaire title", "Nutrition intake and adherence review")
            questions_text = st.text_area("Questions — one per line", "What makes the plan difficult to follow?\nHave symptoms or medications changed?\nWhich meals are most often missed?")
            send_questions = st.form_submit_button("Send questionnaire", type="primary", width="stretch")
        if send_questions:
            try:
                create_questionnaire(
                    str(current_user["id"]), active_profile_id, title,
                    [line.strip() for line in questions_text.splitlines() if line.strip()],
                )
                st.success("Questionnaire sent.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        for questionnaire in list_questionnaires(customer_id=active_profile_id, dietitian_id=str(current_user["id"])):
            with st.expander(f"{questionnaire['status']} · {questionnaire['title']} · {questionnaire['created_at'][:10]}"):
                if questionnaire.get("answers"):
                    for question, answer in questionnaire["answers"].items():
                        st.markdown(f"**{question}**")
                        st.write(answer)
                else:
                    st.caption("Waiting for customer answers.")


def render_admin_governance() -> None:
    if not is_admin:
        st.error("Administrator access is required.")
        return
    hero(
        "Administrator governance",
        "Approve professionals.<br><em>Control clinical access and caseloads.</em>",
        "Approve or reject Dietitian applications, assign customers and audit role access without exposing private clinical notes.",
    )
    applications_tab, assignments_tab, accounts_tab = st.tabs(["Dietitian approvals", "Caseload assignments", "Account directory"])
    with applications_tab:
        applications = [item for item in list_users("Dietitian") if not int(item.get("is_admin", 0))]
        pending = [item for item in applications if item.get("approval_status") == "Pending"]
        if not pending:
            st.success("No Dietitian applications are awaiting approval.")
        for applicant in pending:
            st.markdown(
                f"**{applicant['display_name']}** · @{applicant['username']} · "
                f"Registration: `{applicant.get('credential') or 'Not supplied'}` · {applicant.get('email') or 'No email'}"
            )
            approve_col, reject_col = st.columns(2)
            if approve_col.button("Approve Dietitian", key=f"approve_{applicant['id']}", type="primary", width="stretch"):
                set_dietitian_approval(str(applicant["id"]), str(current_user["id"]), True)
                st.success("Dietitian approved and activated.")
                st.rerun()
            if reject_col.button("Reject application", key=f"reject_{applicant['id']}", width="stretch"):
                set_dietitian_approval(str(applicant["id"]), str(current_user["id"]), False)
                st.warning("Dietitian application rejected.")
                st.rerun()
        if applications:
            st.dataframe(pd.DataFrame(applications)[["display_name", "username", "credential", "approval_status", "active", "created_at"]], width="stretch", hide_index=True)
    with assignments_tab:
        dietitians = [
            item for item in list_users("Dietitian")
            if item.get("approval_status") == "Approved" and int(item.get("active", 0)) and not int(item.get("is_admin", 0))
        ]
        customers = [item for item in list_users("Customer") if int(item.get("active", 0))]
        if dietitians and customers:
            with st.form("admin_caseload_assignment"):
                dietitian_options = {f"{item['display_name']} · {item['credential']}": item["id"] for item in dietitians}
                customer_options = {f"{item['display_name']} · @{item['username']}": item["id"] for item in customers}
                selected_dietitian = st.selectbox("Approved Dietitian", list(dietitian_options))
                selected_customer = st.selectbox("Customer", list(customer_options))
                assign = st.form_submit_button("Assign customer", type="primary", width="stretch")
            if assign:
                set_caseload_assignment(str(dietitian_options[selected_dietitian]), str(customer_options[selected_customer]), True)
                st.success("Caseload assignment activated.")
                st.rerun()
        else:
            st.info("Create at least one approved Dietitian and one Customer before assigning a caseload.")
        links = list_caseload_links()
        if links:
            st.dataframe(pd.DataFrame(links)[["dietitian_name", "customer_name", "status", "created_at"]], width="stretch", hide_index=True)
    with accounts_tab:
        accounts = pd.DataFrame(list_users())
        if not accounts.empty:
            st.dataframe(accounts[["display_name", "username", "role", "approval_status", "active", "is_admin", "created_at", "last_login_at"]], width="stretch", hide_index=True)


def render_care_team() -> None:
    if current_user["role"] != "Customer":
        st.info("Care Team is the customer-facing communication workspace.")
        return
    hero(
        "Customer care workspace", "Your questions and care team.<br><em>Connected without exposing the clinical portal.</em>",
        "View your Administrator-assigned Dietitian, answer questions, receive recommendations and follow active nutrition prescriptions.",
    )
    linked = list_linked_dietitians(str(current_user["id"]))
    if not linked:
        st.info("No Dietitian is assigned yet. The Administrator controls verified clinical assignments.")
        return
    st.subheader("Assigned care team")
    st.dataframe(
        pd.DataFrame(linked)[["display_name", "credential", "email", "created_at"]],
        width="stretch", hide_index=True,
    )
    prescriptions = list_clinical_prescriptions(str(current_user["id"]))
    st.subheader("Nutrition prescriptions")
    if prescriptions:
        st.dataframe(
            pd.DataFrame(prescriptions)[["category", "title", "instructions", "status", "dietitian_name", "created_at"]],
            width="stretch", hide_index=True,
        )
    else:
        st.caption("No nutrition prescriptions have been issued.")
    st.subheader("Assigned questionnaires")
    questionnaires = list_questionnaires(customer_id=str(current_user["id"]))
    for questionnaire in questionnaires:
        with st.expander(f"{questionnaire['status']} · {questionnaire['title']} · from {questionnaire['dietitian_name']}", expanded=questionnaire["status"] == "Open"):
            if questionnaire.get("answers"):
                for question, answer in questionnaire["answers"].items():
                    st.markdown(f"**{question}**")
                    st.write(answer)
            else:
                with st.form(f"answers_{questionnaire['id']}"):
                    answers = {
                        question: st.text_area(question, key=f"answer_{questionnaire['id']}_{index}")
                        for index, question in enumerate(questionnaire["questions"])
                    }
                    if st.form_submit_button("Send answers", type="primary", width="stretch"):
                        if not all(value.strip() for value in answers.values()):
                            st.error("Answer every question before sending.")
                        else:
                            submit_questionnaire(str(questionnaire["id"]), str(current_user["id"]), answers)
                            st.success("Answers sent to your Dietitian.")
                            st.rerun()
    st.subheader("Secure care messages")
    dietitian_options = {item["display_name"]: item["id"] for item in linked}
    selected_name = st.selectbox("Conversation", list(dietitian_options), key="customer_message_dietitian")
    selected_id = str(dietitian_options[selected_name])
    with st.form("customer_message_form"):
        subject = st.text_input("Subject", "Question about my plan")
        body = st.text_area("Message")
        if st.form_submit_button("Send message", type="primary", width="stretch"):
            try:
                send_clinical_message(str(current_user["id"]), selected_id, subject, body)
                st.success("Message sent.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    for message in list_clinical_messages(str(current_user["id"]), selected_id):
        st.markdown(
            f'<div class="np-message"><span>{html.escape(message.get("message_type", "Message"))} · '
            f'{html.escape(message["sender_name"])} → {html.escape(message["recipient_name"])} · '
            f'{html.escape(message.get("status", ""))}</span>'
            f'<h4>{html.escape(message["subject"])}</h4><p>{html.escape(message["body"])}</p>'
            f'<small>{html.escape(message["created_at"][:16].replace("T", " "))} UTC</small></div>',
            unsafe_allow_html=True,
        )


def render_assistant() -> None:
    hero("Plan-aware assistant", "Ask nutrition questions.<br><em>Keep clinical boundaries.</em>", "NutriGuide is grounded in your current profile, verified laboratory signals and active diet plan.")
    api_state = assistant_api_status()
    a1, a2 = st.columns([1, 2])
    a1.metric("Assistant mode", api_state["mode"])
    use_external = False
    with a2:
        if api_state["configured"]:
            consent = st.checkbox("I consent to send the displayed nutrition context to the configured assistant API.")
            use_external = st.toggle("Use configured assistant API", disabled=not consent)
        else:
            st.caption("Built-in assistant is active. Set NUTRIPULSE_ASSISTANT_API_URL and optional NUTRIPULSE_ASSISTANT_API_KEY to enable the secure API adapter.")
    prompts = st.columns(4)
    suggested = ["Analyze my diet plan", "How can I increase protein?", "Explain my lab report", "How does calorie target work?"]
    for column, text in zip(prompts, suggested):
        if column.button(text, width="stretch"):
            response = answer_question(text, profile, st.session_state.plan, st.session_state.lab_results, use_external=use_external)
            st.session_state.chat.extend([{"role":"user","content":text},{"role":"assistant","content":response}])
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    if question := st.chat_input("Ask about your nutrition plan, food or safety checks…"):
        response = answer_question(question, profile, st.session_state.plan, st.session_state.lab_results, use_external=use_external)
        st.session_state.chat.extend([{"role":"user","content":question},{"role":"assistant","content":response}])
        st.rerun()


def render_quality_classifier() -> None:
    hero(
        "Portable classical ML model",
        "Classify any food profile.<br><em>See why the model decided.</em>",
        "The bundled portable Random Forest uses calories, macronutrients, fibre, sugar, sodium and nutrient density to classify any entered food as Strong, Balanced or Limit.",
        "No SciPy or scikit-learn import at application startup",
    )
    status = model_status()
    ready = status.get("status") == "Ready"
    summary_columns = st.columns(4)
    summary_columns[0].metric("Model status", status.get("status", "Unknown"))
    summary_columns[1].metric("Accuracy", f"{status.get('accuracy', 0):.1%}" if status.get("accuracy") else "—")
    summary_columns[2].metric("Macro F1", f"{status.get('macro_f1', 0):.1%}" if status.get("macro_f1") else "—")
    summary_columns[3].metric("Training records", f"{status.get('samples', 0):,}" if status.get("samples") else "—")
    if not ready:
        st.error(status.get("message", "The portable nutrition classifier is unavailable."))
        if st.button("Reload and verify portable classifier", type="primary", width="stretch"):
            train_quality_model(frame)
            st.success("Portable nutrition classifier verified.")
            st.rerun()
        return

    dataset_tab, manual_tab = st.tabs(["Classify a dataset food", "Enter nutrients manually"])
    with dataset_tab:
        query = st.text_input("Search food", placeholder="e.g., apple, chicken, yogurt", key="classifier_food_search")
        matches = search_foods_smart(frame, query, limit=100) if query else frame.sort_values("healthy_rank_score", ascending=False).head(100)
        if matches.empty:
            st.warning("No matching food was found. Try fewer words or use manual nutrient entry.")
        else:
            selection = st.selectbox("Food record", matches["food_name"].tolist(), key="classifier_food_record")
            food = matches[matches["food_name"] == selection].iloc[0].to_dict()
            inputs = st.columns(7)
            for column, label, field, suffix in zip(
                inputs,
                ["Calories", "Protein", "Carbs", "Fat", "Fibre", "Sugar", "Sodium"],
                ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg"],
                [" kcal", " g", " g", " g", " g", " g", " mg"],
            ):
                column.metric(label, f"{float(food[field]):.1f}{suffix}")
            if st.button("Run nutrition classifier", type="primary", width="stretch", key="classify_dataset_food"):
                st.session_state.quality_result = predict_quality(food)
                st.session_state.quality_input_name = selection
                st.session_state.quality_input_food = food
    with manual_tab:
        with st.form("manual_quality_classifier"):
            manual_name = st.text_input("Food name", "Custom food")
            manual_category = st.selectbox("Food category", sorted(frame["food_type"].unique().tolist()))
            r1 = st.columns(4)
            calories = r1[0].number_input("Calories", 0.0, 3000.0, 300.0, 10.0)
            protein_g = r1[1].number_input("Protein (g)", 0.0, 250.0, 15.0, 1.0)
            carbs_g = r1[2].number_input("Carbs (g)", 0.0, 500.0, 35.0, 1.0)
            fat_g = r1[3].number_input("Fat (g)", 0.0, 250.0, 10.0, 1.0)
            r2 = st.columns(3)
            fiber_g = r2[0].number_input("Fibre (g)", 0.0, 100.0, 5.0, 1.0)
            sugar_g = r2[1].number_input("Sugar (g)", 0.0, 250.0, 5.0, 1.0)
            sodium_mg = r2[2].number_input("Sodium (mg)", 0.0, 10000.0, 250.0, 10.0)
            classify_manual = st.form_submit_button("Classify custom nutrient profile", type="primary", width="stretch")
        if classify_manual:
            food = {
                "food_name": manual_name.strip() or "Custom food", "food_type": manual_category,
                "calories": calories, "protein_g": protein_g, "carbs_g": carbs_g,
                "fat_g": fat_g, "fiber_g": fiber_g, "sugar_g": sugar_g,
                "sodium_mg": sodium_mg,
            }
            st.session_state.quality_result = predict_quality(food)
            st.session_state.quality_input_name = food["food_name"]
            st.session_state.quality_input_food = food

    if st.session_state.quality_result:
        st.subheader("Classification result")
        render_quality_result(
            st.session_state.quality_result,
            st.session_state.quality_input_name or "Food",
            st.session_state.quality_input_food,
        )
    with st.expander("How this classifier works"):
        st.write(
            "The target labels are derived from the dataset's healthy-rank score. A preprocessing pipeline "
            "standardizes numeric values, one-hot encodes food category, and passes the features into a "
            "class-balanced portable Random Forest. The shown confidence is the model probability, not clinical certainty."
        )
        st.caption(f"Runtime: {status.get('runtime', 'Pure Python')} · Training samples: {status.get('samples', 0):,}")


def render_web_and_api() -> None:
    hero(
        "Trusted web intelligence + developer API",
        "Connect verified sources.<br><em>Build on a real backend.</em>",
        "Extract compact previews from curated evidence, public web pages and public JSON/data APIs, then use NutriPulse through a documented FastAPI service.",
        "Source attribution · SSRF protection · OpenAPI docs",
    )
    web_visual = ASSET_DIR / "web_insights.jpg"
    if web_visual.exists():
        st.image(str(web_visual), caption="Evidence extraction and API connectivity", width="stretch")

    web_tab, api_tab = st.tabs(["Trusted web insights", "FastAPI developer service"])
    with web_tab:
        metrics = st.columns(4)
        metrics[0].metric("Curated sources", len(TRUSTED_SOURCES))
        metrics[1].metric("Response limit", "1.5 MB")
        metrics[2].metric("Cache duration", "30 min")
        metrics[3].metric("Network policy", "Public web only")

        source_labels = {source["name"]: source for source in TRUSTED_SOURCES}
        mode = st.radio(
            "Source mode",
            ["Curated evidence", "Public web page", "Public JSON / data API"],
            horizontal=True,
        )
        request_headers: dict[str, str] = {}
        if mode == "Curated evidence":
            source_name = st.selectbox("Nutrition evidence source", list(source_labels))
            selected_source = source_labels[source_name]
            target_url = selected_source["url"]
            st.caption(selected_source["description"])
        else:
            target_url = st.text_input(
                "Public URL",
                placeholder=(
                    "https://www.who.int/news-room/fact-sheets/detail/healthy-diet"
                    if mode == "Public web page" else "https://api.example.org/v1/nutrition?food=apple"
                ),
            )
            st.caption("Any public HTTP(S) domain is supported. Local/private networks, credentials in URLs, unsafe redirects and oversized responses are blocked.")
            if mode == "Public JSON / data API":
                authentication = st.radio(
                    "API authentication", ["None", "Bearer token", "API-key header"],
                    horizontal=True,
                )
                if authentication == "Bearer token":
                    token = st.text_input("Bearer token (session only)", type="password")
                    if token:
                        request_headers["Authorization"] = f"Bearer {token}"
                elif authentication == "API-key header":
                    header_columns = st.columns([0.7, 1.3])
                    header_name = header_columns[0].text_input("Header name", value="X-API-Key")
                    header_value = header_columns[1].text_input("API key (session only)", type="password")
                    if header_name and header_value:
                        request_headers[header_name] = header_value

        if st.button("Fetch and extract source / API", type="primary", width="stretch", disabled=not target_url):
            try:
                with st.spinner("Validating the public destination and extracting a compact preview…"):
                    if mode == "Curated evidence":
                        st.session_state.web_article = cached_web_article(target_url)
                    else:
                        st.session_state.web_article = fetch_public_resource(
                            target_url, request_headers=request_headers,
                        )
                st.success("Source extracted. Review its attribution and retrieval status below.")
            except WebInsightError as exc:
                st.session_state.web_article = None
                st.error(str(exc))

        article = st.session_state.get("web_article")
        if article:
            st.subheader(article["title"])
            details = st.columns(4)
            details[0].metric("Domain", article["domain"])
            details[1].metric("Extracted words", article["word_count"])
            details[2].metric("Content blocks", article["paragraph_count"])
            details[3].metric("Resource", article.get("resource_type", "web page").replace("-", " ").title())
            if article.get("live_access") is False:
                st.warning(
                    f"The official site returned HTTP {article.get('live_http_status', 'blocked')}. "
                    "NutriPulse loaded its clearly labeled bundled source summary; use Open original source for verification."
                )
            if article.get("description"):
                st.info(article["description"])
            if article.get("data_preview") is not None:
                with st.expander("Structured API response preview", expanded=True):
                    st.json(article["data_preview"])
            keyword = st.text_input("Filter extracted text", placeholder="e.g., salt, fruit, vitamin")
            paragraphs = article["paragraphs"]
            if keyword.strip():
                paragraphs = [paragraph for paragraph in paragraphs if keyword.lower() in paragraph.lower()]
            if not paragraphs:
                st.warning("No extracted content matches this filter.")
            for index, paragraph in enumerate(paragraphs, 1):
                st.markdown(
                    f'<div class="np-source-card"><span>EXTRACT {index:02d}</span><p>{html.escape(paragraph)}</p></div>',
                    unsafe_allow_html=True,
                )
            download_columns = st.columns(3)
            download_columns[0].link_button("Open original source", article["url"], width="stretch")
            download_columns[1].download_button(
                "Download JSON",
                json.dumps(article, indent=2, ensure_ascii=False).encode("utf-8"),
                "nutripulse_web_insight.json",
                "application/json",
                width="stretch",
            )
            download_columns[2].download_button(
                "Download Markdown",
                article_to_markdown(article),
                "nutripulse_web_insight.md",
                "text/markdown",
                width="stretch",
            )
            st.warning(
                "Web extracts are not automatically used to diagnose conditions or alter diet plans. "
                "Verify the original source and consult a qualified professional for patient-specific decisions."
            )
        else:
            st.info("Choose curated evidence, a public page, or a public GET API. Live web access is required only for this feature; the rest of NutriPulse remains local-first.")

    with api_tab:
        api_url = os.getenv("NUTRIPULSE_API_URL", "http://127.0.0.1:8000").rstrip("/")
        status_columns = st.columns(4)
        status_columns[0].metric("API version", APP_VERSION)
        status_columns[1].metric("Endpoints", 18)
        status_columns[2].metric("Schema", "OpenAPI 3")
        status_columns[3].metric("Protection", "Optional API key")
        st.markdown(
            '<div class="np-alert"><span>⌁</span><div><strong>Start the full stack</strong><br>'
            '<small>Windows: double-click START_ALL.bat · macOS/Linux: run the Streamlit and API launch scripts in separate terminals.</small></div></div>',
            unsafe_allow_html=True,
        )
        controls = st.columns(2)
        controls[0].link_button("Open Swagger API documentation", f"{api_url}/docs", width="stretch")
        if controls[1].button("Test API connection", width="stretch"):
            try:
                response = requests.get(f"{api_url}/health", timeout=3)
                response.raise_for_status()
                payload = response.json()
                st.success(
                    f"API connected · {payload.get('food_records', 0):,} food records · "
                    f"vision {payload.get('food_vision', 'unknown')}"
                )
            except (requests.RequestException, ValueError) as exc:
                st.error(f"API is not reachable at {api_url}. Start START_API.bat or START_ALL.bat. Details: {exc}")

        endpoints = pd.DataFrame([
            ["GET", "/health", "Service and model readiness"],
            ["GET", "/api/v1/foods/search", "Search the nutrition dataset"],
            ["POST", "/api/v1/classifier/predict", "Classify a nutrient profile"],
            ["POST", "/api/v1/labs/analyze", "Flag verified laboratory values"],
            ["POST", "/api/v1/diet/plan", "Generate a safety-gated 7-day plan"],
            ["POST", "/api/v1/vision/predict", "Run Food-101 image inference"],
            ["POST", "/api/v1/vision/analyze", "Analyze an uploaded image with nutrition estimates"],
            ["POST", "/api/v1/vision/analyze-url", "Safely analyze a direct public image URL"],
            ["POST", "/api/v1/diary/vision-url", "Analyze a public image URL and add the confirmed estimate to a profile diary"],
            ["GET", "/api/v1/diary", "Read a profile food diary"],
            ["POST", "/api/v1/assistant/ask", "Use the grounded assistant or configured consent-gated API adapter"],
            ["GET", "/api/v1/schedule", "Read past and future meal schedule records"],
            ["POST", "/api/v1/schedule/{meal_id}/status", "Clear, skip, or restore a scheduled meal"],
            ["POST", "/api/v1/alerts/evaluate", "Evaluate clinical-safe alert rules"],
            ["GET", "/api/v1/alerts", "List persisted patient alerts"],
            ["POST", "/api/v1/alerts/{id}/acknowledge", "Acknowledge an active alert"],
            ["POST", "/api/v1/web/scrape", "Extract an allowlisted evidence page"],
            ["POST", "/api/v1/web/extract", "Extract a public GET page or JSON/XML/text API"],
        ], columns=["Method", "Endpoint", "Purpose"])
        st.dataframe(endpoints, width="stretch", hide_index=True)
        st.code(
            f'curl "{api_url}/api/v1/foods/search?q=apple&limit=5"',
            language="bash",
        )
        st.caption("If NUTRIPULSE_API_KEY is set, add: -H \"X-API-Key: your-secret\". Never commit the real key.")


def render_admin() -> None:
    if not is_admin:
        st.error("Administrator access is required.")
        return
    hero("Data, ML and governance", "All 76,920 source rows.<br><em>Every purpose visible and auditable.</em>", "Inspect the nine-dataset integration, trace every supplied row, verify the portable classical ML model and monitor deployment readiness.")
    quality = dataset_quality(frame)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Food records", f"{quality['rows']:,}")
    c2.metric("Categories", quality["categories"])
    c3.metric("Numeric missing", quality["missing_numeric"])
    c4.metric("Potential duplicates", quality["duplicates"])
    c5.metric("Memory", f"{quality['memory_mb']} MB")
    manifest_path = DATA_DIR / "dataset_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        audit = manifest.get("source_audit", {})
        audit_cards = st.columns(6)
        audit_cards[0].metric("All source rows", f"{audit.get('raw_source_records', 0):,}")
        audit_cards[1].metric("Food-related rows", f"{audit.get('food_related_source_records', 0):,}")
        audit_cards[2].metric("Nutrition candidates", f"{audit.get('nutrition_candidate_input_records', 0):,}")
        audit_cards[3].metric("Classifier-ready unique", f"{audit.get('classifier_ready_unique_records', 0):,}")
        audit_cards[4].metric("Safety-source rows", f"{audit.get('safety_source_records', 0):,}")
        audit_cards[5].metric("Person benchmarks", f"{audit.get('benchmark_source_records', 0):,}")
        st.markdown(
            f'<div class="np-command-note"><b>Nine-dataset build:</b> '
            f'{audit.get("raw_source_records", 0):,} total supplied rows are registered. '
            f'{audit.get("filtered_or_deduplicated_nutrition_records", 0):,} nutrition-candidate rows were filtered or deduplicated '
            f'to prevent repeated or invalid classifier examples. Public builds retain aggregate lineage only; '
            f'authorized local builds may include the private row-level registry.</div>',
            unsafe_allow_html=True,
        )
        with st.expander("Dataset lineage and purpose-aware integration"):
            if audit.get("by_file"):
                st.dataframe(pd.DataFrame(audit["by_file"]), width="stretch", hide_index=True)
            st.json(manifest, expanded=False)
        registry_path = DATA_DIR / "source_record_registry.csv"
        if registry_path.exists():
            with st.expander("Search the complete 76,920-row source registry"):
                registry = pd.read_csv(registry_path, low_memory=False)
                source_filter = st.selectbox("Source dataset", ["All datasets", *sorted(registry["source_file"].unique())])
                record_query = st.text_input("Food, product or source record search")
                filtered = registry
                if source_filter != "All datasets":
                    filtered = filtered[filtered["source_file"] == source_filter]
                if record_query.strip():
                    filtered = filtered[filtered["record_name"].fillna("").str.contains(record_query.strip(), case=False, regex=False)]
                st.caption(f"Showing {min(len(filtered), 500):,} of {len(filtered):,} matching source rows.")
                st.dataframe(filtered.head(500), width="stretch", hide_index=True, height=420)
    left, right = st.columns([1.2, .8])
    with left:
        counts = frame["food_type"].value_counts().reset_index()
        counts.columns = ["Category","Foods"]
        fig = px.bar(counts, x="Foods", y="Category", orientation="h", title="Dataset category distribution", color="Foods", color_continuous_scale=[[0,"#16423c"],[1,"#b9f06a"]])
        st.plotly_chart(plot_layout(fig, 430), width="stretch", config={"displayModeBar":False})
    with right:
        status = model_status()
        st.markdown('<div class="np-panel"><div class="np-eyebrow">MODEL REGISTRY</div><h3>Nutrition quality classifier</h3></div>', unsafe_allow_html=True)
        if status.get("status") == "Ready":
            st.success("Portable Random Forest is loaded without SciPy/scikit-learn runtime imports.")
            model_metrics = st.columns(3)
            model_metrics[0].metric("Accuracy", f"{status.get('accuracy', 0):.1%}")
            model_metrics[1].metric("Macro F1", f"{status.get('macro_f1', 0):.1%}")
            model_metrics[2].metric("Test records", f"{status.get('test_samples', 0):,}")
            st.caption("Open ◆ Nutrition Classifier from the sidebar to test dataset foods or custom nutrient values.")
        else:
            st.error(status.get("message", status.get("status", "Model unavailable")))
        if st.button("Verify portable Random Forest model", type="primary", width="stretch"):
            metrics = train_quality_model(frame)
            st.success(f"Model verified · accuracy {metrics['accuracy']:.1%} · macro F1 {metrics['macro_f1']:.1%}")
            st.rerun()
        with st.expander("Nutrition model card and evaluation details"):
            st.json(status, expanded=True)
        st.markdown("**Food vision model**")
        vision_status = food_vision_status()
        if vision_status["status"] == "Ready":
            st.success("Bundled MobileNetV2 Food-101 model is ready.")
        else:
            st.error(vision_status["message"])
        vision_metrics = st.columns(3)
        vision_metrics[0].metric("Classes", vision_status.get("classes", 0))
        vision_metrics[1].metric("Top-1 benchmark", f"{vision_status.get('reported_top1_accuracy', 0):.1%}" if vision_status.get("reported_top1_accuracy") else "—")
        vision_metrics[2].metric("Integrity", vision_status.get("integrity", "Unavailable"))
        with st.expander("Vision model details and limitations"):
            st.json(vision_status, expanded=True)
    st.subheader("Deployment readiness")
    readiness = pd.DataFrame([
        ["SQLite persistence", "Ready", "Profiles, reports, plans, diaries, progress and reviews"],
        ["Role-based accounts", "Ready", "PBKDF2 passwords, separated Customer/Dietitian/Admin workspaces and approval gates"],
        ["Lab OCR", "Ready with fallback", "Bundled RapidOCR for images/scanned PDFs; Tesseract remains optional"],
        ["Clinical safety rules", "Ready for prototype", "Requires jurisdiction-specific expert validation"],
        ["Classical ML", "Ready", "Portable Random Forest with held-out evaluation; no SciPy startup dependency"],
        ["Deep learning vision", vision_status["status"], "Bundled MobileNetV2 with ONNX Runtime and Windows-safe OpenCV DNN fallback"],
        ["FastAPI service", "Ready", "Versioned endpoints, Swagger/ReDoc, validation, CORS and optional API-key protection"],
        ["Trusted web extraction", "Ready", "Allowlisted domains, public-network enforcement, size limits, caching and source attribution"],
        ["Clinical alert center", "Ready", "Persisted severity rules, lab and lifestyle signals, history and acknowledgement workflow"],
        ["External EHR / wearables", "Integration point", "Requires authorized APIs and consent"],
    ], columns=["Capability","Status","Notes"])
    st.dataframe(readiness, width="stretch", hide_index=True)


customer_pages = {
    "◈  Overview": render_dashboard,
    "◉  Alert Center": render_alert_center,
    "◎  My Profile": render_profile,
    "⌁  Laboratory Intelligence": render_labs,
    "▦  Smart Diet Planner": render_plan,
    "◉  Food Vision & Diary": render_vision_diary,
    "⌕  Food Library": render_food_library,
    "↗  Progress Analytics": render_progress,
    "✦  Care Team": render_care_team,
    "✧  NutriGuide Assistant": render_assistant,
    "◆  Nutrition Classifier": render_quality_classifier,
    "⌘  Evidence Web & API": render_web_and_api,
}
dietitian_pages = {
    "✦  Clinical Dashboard": render_clinical_dashboard,
    "◈  Customer Overview": render_clinical_overview,
    "◉  Food Diary Review": render_clinical_diary,
    "▦  Diet Plan Oversight": render_clinical_plans,
    "⌁  Reports & Lab Analysis": render_clinical_reports,
    "↗  Progress Analytics": render_clinical_progress,
    "◆  Notes & Prescriptions": render_clinical_notes_and_prescriptions,
    "✉  Questions & Messaging": render_clinical_messages,
}
admin_pages = {
    **dietitian_pages,
    "⚙  Administrator Governance": render_admin_governance,
    "⌘  Dataset & Model Audit": render_admin,
}
pages = admin_pages if is_admin else (dietitian_pages if current_user["role"] == "Dietitian" else customer_pages)
requested_page = st.session_state.pop("workspace_page_requested", None)
if requested_page in pages:
    st.session_state.workspace_page = requested_page
elif st.session_state.get("workspace_page") not in pages:
    st.session_state.workspace_page = next(iter(pages))
selected_page = st.sidebar.radio(
    "Workspace", list(pages), label_visibility="collapsed", key="workspace_page",
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    f'<div class="np-user-chip"><span>{"Administrator" if is_admin else html.escape(str(current_user["role"]))}</span>'
    f'<strong>{html.escape(str(current_user["display_name"]))}</strong>'
    f'<small>@{html.escape(str(current_user["username"]))}</small></div>',
    unsafe_allow_html=True,
)
if st.sidebar.button("Sign out", width="stretch"):
    st.session_state.clear()
    st.rerun()
active_alert_count = sum(item["status"] == "Active" for item in current_alerts)
alert_tone = "critical" if any(item["severity"] == "Critical" and item["status"] == "Active" for item in current_alerts) else "normal"
st.sidebar.markdown(
    f'<div class="np-sidebar-alert {alert_tone}"><span>◆</span><div><strong>{active_alert_count} active alert(s)</strong>'
    '<small>Open Alert Center for the safety queue</small></div></div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown('<span class="np-badge"><i class="np-dot"></i>Safety layer active</span>', unsafe_allow_html=True)
st.sidebar.caption(f"{APP_SUBTITLE}\n\nVersion {APP_VERSION} · Local-first · SQLite storage")
st.markdown(
    f'<div class="np-command-bar"><div><span class="np-command-orb"></span><b>NutriPulse Intelligence</b>'
    f'<small>{html.escape(selected_page.replace("  ", " "))}</small></div>'
    f'<div class="np-command-status"><span>{active_alert_count} alerts</span><span>API-ready</span><span>Local data boundary</span></div></div>',
    unsafe_allow_html=True,
)
pages[selected_page]()
footer()
