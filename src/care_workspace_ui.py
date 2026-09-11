"""Shared care-workspace pages for customer, dietitian and administrator portals."""
from __future__ import annotations

import streamlit as st

from .account_security import list_account_events, revoke_account_sessions
from .care_tasks import (
    TASK_PRIORITIES, TASK_STATUSES, create_care_task, list_care_tasks, list_task_events,
    mark_conversation_read, task_summary, unread_conversations, update_care_task,
)
from .database import list_clinical_messages, list_linked_dietitians, list_users, send_clinical_message
from .local_time import local_today


def render_conversation(user_id: str, partner_id: str, key_prefix: str) -> None:
    messages = list_clinical_messages(user_id, partner_id)[-50:]
    unread_ids = [str(item["id"]) for item in messages if item["recipient_id"] == user_id and not item["read_at"]]
    if not messages:
        st.info("Start a conversation using the message form.")
        return
    st.caption("Most recent 50 messages. Read receipts change when you mark the displayed messages as read.")
    if unread_ids and st.button("Mark displayed messages as read", key=f"{key_prefix}_mark_read"):
        mark_conversation_read(user_id, partner_id, unread_ids)
        st.rerun()
    for message in messages:
        receipt = "Read" if message["read_at"] else ("Unread" if message["recipient_id"] == user_id else "Delivered")
        with st.container(border=True):
            st.caption(f"{message['sender_name']} → {message['recipient_name']} · {receipt}")
            st.text(message["subject"])
            st.text(message["body"])
            st.caption(f"{message['created_at'][:16].replace('T', ' ')} UTC · {message.get('message_type', 'Message')}")


def render_inbox(current_user: dict, linked_customers: list[dict]) -> None:
    st.title("Care Inbox")
    st.write("Keep care conversations together and track unread messages.")
    user_id = str(current_user["id"])
    unread = {str(item["sender_id"]): int(item["unread_count"]) for item in unread_conversations(user_id)}
    st.metric("Unread messages", sum(unread.values()))
    partners = {}
    for item in reversed(list_clinical_messages(user_id)):
        sent = item["sender_id"] == user_id
        partners[str(item["recipient_id"] if sent else item["sender_id"])] = item["recipient_name"] if sent else item["sender_name"]
    available = (list_users() if current_user.get("is_admin") else linked_customers) if current_user["role"] == "Dietitian" else list_linked_dietitians(user_id)
    for person in available:
        if str(person["id"]) != user_id:
            partners[str(person["id"])] = str(person["display_name"])
    if not partners:
        st.info("Your assigned care-team conversations will appear here.")
        return
    partner_id = st.selectbox(
        "Conversation", list(partners), key="inbox_partner",
        format_func=lambda uid: f"{partners[uid]} · {unread.get(uid, 0)} unread · {uid[:8]}",
    )
    render_conversation(user_id, partner_id, "inbox")
    with st.form("inbox_compose", clear_on_submit=True):
        subject = st.text_input("Subject", max_chars=160)
        body = st.text_area("Message", max_chars=4000)
        if st.form_submit_button("Send message", type="primary", width="stretch"):
            try:
                send_clinical_message(user_id, partner_id, subject, body)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def render_care_tasks(current_user: dict, active_profile_id: str, profile: dict,
                      linked_customers: list[dict]) -> None:
    st.title("Care Tasks")
    st.write("Follow up on agreed actions with due dates, priorities, and a shared status history.")
    if current_user["role"] == "Dietitian" and not linked_customers:
        st.info("Select an assigned customer when a caseload is available.")
        return
    user_id = str(current_user["id"])
    tasks = list_care_tasks(user_id, active_profile_id)
    counts = task_summary(tasks)
    for column, label, key in zip(st.columns(4), ("Active", "Due today", "Overdue", "Completed"), ("open", "today", "overdue", "completed")):
        column.metric(label, counts[key])
    st.caption(f"Customer: {profile['name']} · Today: {local_today().strftime('%d %b %Y')}")
    with st.expander("Create a care task"):
        with st.form("care_task_create", clear_on_submit=True):
            title = st.text_input("Task title", max_chars=160, placeholder="Bring your food diary to the next review")
            instructions = st.text_area("Instructions", max_chars=2000)
            due = st.date_input("Due date", value=local_today(), min_value=local_today())
            priority = st.selectbox("Priority", TASK_PRIORITIES)
            if st.form_submit_button("Create task", type="primary", width="stretch"):
                try:
                    create_care_task(user_id, active_profile_id, title, instructions, due.isoformat(), priority)
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
    view = st.selectbox("Show tasks", ("Active", "Due today", "Overdue", "Completed", "All"))
    query = st.text_input("Search tasks", max_chars=160).strip().casefold()
    today = local_today().isoformat()
    filtered = []
    for task in tasks:
        active = task["status"] in {"Open", "In progress"}
        matches = {"All": True, "Active": active, "Due today": active and task["due_date"] == today,
                   "Overdue": active and task["due_date"] < today, "Completed": task["status"] == "Completed"}
        if matches[view] and query in f"{task['title']} {task['instructions']}".casefold():
            filtered.append(task)
    if not filtered:
        st.info("No tasks match this view.")
        return
    page_count = max(1, (len(filtered) + 19) // 20)
    page = st.selectbox("Task page", range(1, page_count + 1))
    st.caption(f"{len(filtered)} matching tasks · 20 per page")
    for task in filtered[(page - 1) * 20:page * 20]:
        with st.container(border=True):
            st.subheader(task["title"])
            due_label = "Overdue" if task["due_date"] < today and task["status"] in {"Open", "In progress"} else "Due"
            st.caption(f"{task['status']} · {task['priority']} priority · {due_label} {task['due_date']} · Created by {task['created_by_name']}")
            if task["instructions"]:
                st.text(task["instructions"])
            if task["status"] != "Cancelled":
                options = list(TASK_STATUSES)
                if current_user["role"] == "Customer" and task["created_by"] != user_id:
                    options.remove("Cancelled")
                with st.form(f"care_status_{task['id']}_{task['revision']}"):
                    new_status = st.selectbox("Task status", options, index=options.index(task["status"]))
                    if st.form_submit_button("Update status", width="stretch"):
                        try:
                            if update_care_task(user_id, task["id"], new_status, expected_revision=task["revision"]):
                                st.rerun()
                            else:
                                st.warning("Someone updated this task. Refresh the page to review their changes before saving.")
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))
            with st.expander("Task history"):
                st.dataframe(list_task_events(user_id, task["id"]), hide_index=True, width="stretch")


def render_account_security(current_user: dict, persist_audio_preferences) -> None:
    st.title("Account & Security")
    st.write("Manage your saved audio preferences and access to your account.")
    st.text(f"{current_user['display_name']} · {current_user.get('email') or current_user['username']}")
    st.subheader("Audio preferences")
    st.toggle("Voice replies", key="assistant_voice_enabled", on_change=persist_audio_preferences, args=(str(current_user["id"]),))
    st.toggle("Message sounds", key="assistant_sound_enabled", on_change=persist_audio_preferences, args=(str(current_user["id"]),))
    if current_user["role"] != "Customer":
        st.toggle("Voice alerts", key="voice_alerts_enabled", on_change=persist_audio_preferences, args=(str(current_user["id"]),))
    else:
        st.caption("Voice alerts can be changed in the sidebar.")
    st.caption("Preferences stay saved until you change them. Your browser may need a tap before it can play audio on a new device.")
    st.subheader("Account sessions")
    st.write("Sessions end after one hour without interaction or twelve hours after sign-in. Password recovery signs out existing sessions.")
    confirmed = st.checkbox("Sign me out of every open NutriPulse session")
    if st.button("Sign out everywhere", disabled=not confirmed, width="stretch"):
        revoke_account_sessions(str(current_user["id"]))
        st.session_state.clear()
        st.session_state.entry_view = "auth"
        st.rerun()
    st.subheader("Recent account activity")
    events = list_account_events(str(current_user["id"]))
    if events:
        st.dataframe(events, width="stretch", hide_index=True)
        st.caption("Most recent 100 recorded events. Times are UTC.")
    else:
        st.info("New sign-ins, password changes, and sign-outs will appear here.")
