# Changelog

## 4.5.0 — 2026-08-30

- Added persistent PostgreSQL storage activated by `NUTRIPULSE_DATABASE_URL` for Streamlit Community Cloud and other ephemeral hosts.
- Retained automatic SQLite storage for local Windows installations and explicit isolated test databases.
- Added Administrator storage health indicators and an explicit cloud reboot-safety warning.
- Added a conflict-safe utility for importing a private SQLite backup into PostgreSQL.
- Updated all username, schedule and schema operations for PostgreSQL/SQLite compatibility.

## 4.3.0 — 2026-08-29

- Added persistent active-day tracking derived from the saved SQLite meal schedule.
- Completing the final meal of a day now opens and selects the next incomplete day automatically.
- Completing all seven days records the finished week and creates the next seven-day cycle from the same reviewed plan.
- Added locked future-day previews so meals are completed in sequence while completed history remains reviewable.
- Added customer daily completion charts, week-by-week trajectory, completed-week metrics and a formal week-history table.
- Added matching Dietitian/Admin longitudinal schedule analytics for every assigned customer.
- Extended schedule API responses with active day, week number, daily summaries, weekly summaries and transition details.
- Added an OpenCV DNN Food Vision fallback so a blocked optional ONNX Runtime DLL no longer prevents Windows startup.
- Pinned the optional ONNX Runtime Windows wheel to 1.20.1 and expanded regression coverage to 44 tests.

## 4.2.0 — 2026-08-28

- Replaced external-only image OCR with bundled RapidOCR and retained Tesseract as a fallback.
- Added scanned-PDF rendering/OCR, PDF table extraction and 21 additional common laboratory rules.
- Fixed persistent Streamlit editor state that reused the demonstration values after a new report upload.
- Changed the laboratory editor to accept additional extracted test names with unverified-range safeguards.
- Added public GET extraction for JSON, XML, CSV, text and HTML with session-only Bearer/API-key headers.
- Preserved SSRF, redirect, port and response-size controls for arbitrary public API destinations.
- Added clearly labeled curated-source fallback summaries for official sites returning HTTP 403/429.
- Prevented low-confidence Food-101 output from automatically attaching an unrelated nutrition record.
- Added actual-dish confirmation, regional-food reranking, biryani/pulao aliases and API `dish_hint` support.
- Expanded regression coverage to 41 unit/API tests.

## 4.1.0 — 2026-08-28

- Added a separate Dietitian application flow with inactive-until-approved accounts.
- Added protected first-Administrator setup, Dietitian approval/rejection and caseload assignment.
- Removed Customer features from Dietitian navigation and added eight dedicated clinical workspaces.
- Added assigned-customer dashboard, Admin full-customer override and role-aware routing.
- Added customer vitals/risk overview, complete diary review and daily calorie charts.
- Added Dietitian report analysis, safety-gated plan generation and formal acting-role reviews.
- Added Customer-hidden private clinical notes and Customer-visible nutrition prescriptions.
- Added Question/Recommendation threads that mark open questions answered after Customer reply.
- Added a 76,920-row source registry and explicit reconciliation of all nine datasets.
- Corrected sparse progress charts so a single date no longer renders microsecond x-axis labels.
- Added a self-diagnosing Windows launcher and `NUTRIPULSE_STARTUP_LOG.txt` on failure.

## 4.0.0 — 2026-08-28

- Added Customer and Dietitian username/password accounts with PBKDF2-SHA256 hashing.
- Added per-account profiles, plans, diaries, alerts, progress, questionnaires, and messages.
- Added Dietitian registration/license and invite-code gating.
- Added a role-hidden Dietitian Clinical Hub with customer selection, risk overview, questionnaires, secure messages, and plan-review queue.
- Added Customer Care Team for Dietitian connections, questionnaire answers, and replies.
- Added Monday–Sunday meal schedules generated with every saved plan.
- Added Clear meal, Skip, Restore, and Undo controls.
- Added a live 60-second meal reminder watcher, due/overdue alerts, and persistent alert history.
- Added completion analytics for the current week, history, and future schedule.
- Integrated all nine supplied datasets into a purpose-aware data layer.
- Added a 47,152-record master food index, a 4,590-record safety registry, and 6,000-row intake benchmarks.
- Replaced the SciPy/scikit-learn startup path with a portable pure-Python Random Forest runtime.
- Added assistant API status, consent-gated external adapter, and `POST /api/v1/assistant/ask`.
- Added API endpoints for internet-image diary logging, diary reads, meal schedules, and meal status updates.
- Preserved Food-101 ONNX inference, public image URL safety checks, laboratory gates, report exports, and evidence extraction.
- Added root-level one-click and VS Code launchers.
- Expanded automated coverage to Customer and Dietitian UI pages.

## 3.2.0

- Added direct public-image URL analysis, Food Vision nutrition estimates, food-specific alerts, and the obsidian/emerald/champagne interface.
