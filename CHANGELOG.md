# Changelog

## 4.10.0 — 2026-09-01

- Added approved-Dietitian live presence with a 60-second authenticated heartbeat and configurable five-minute inactivity window.
- Restricted presence visibility to active Administrator-assigned caseload links; unrelated Customers never receive another Dietitian's status.
- Added **DIETITIAN IS LIVE** customer banner, toast and persistent Alert Center state, with immediate explicit sign-out clearing.
- Upgraded NutriGuide with plan/lab explanation, groceries, allergy-aware meal substitutions, plan-linked recipes and saved weekly-progress summaries.
- Added transparent assistant intent, confidence, grounding and clinical-review metadata to Streamlit and FastAPI responses.
- Added optional dependency-free message chimes, disabled by default, without loading third-party audio resources.
- Added real browser text-to-speech for NutriGuide replies, replay control and opt-in spoken Dietitian-live, meal and critical alerts.
- Added a top-right Customer Care Team status card that explicitly shows **DIETITIAN IS LIVE** or **DIETITIAN IS OFFLINE**.
- Expanded automated regression coverage to presence expiry/isolation, live alerts, assistant actions and audio generation.

## 4.9.0 — 2026-08-31

- Added report-specific clinical nutrition strategies that change meal choices, macro targets, fibre targets and preparation guidance from verified laboratory findings and customer conditions.
- Added transparent laboratory-to-plan traceability with a per-report fingerprint, value-level plan response and a visible “Why this plan is different” explanation.
- Restored each customer’s latest verified laboratory report from persistent storage after app restart or customer switching so planning no longer silently falls back to an empty report.
- Added clinician-only renal, electrolyte and thyroid safeguards, while retaining critical-result plan blocking and professional-review status.
- Added distinct glucose, lipid, vitamin D, B-vitamin, blood-count, inflammation, liver, urate and lower-sodium meal adaptations plus regression coverage.


## 4.8.1 — 2026-08-31

- Fixed Administrator and Dietitian Customer Overview so flagged conditions and allergies render as alerts without exposing Streamlit `DeltaGenerator` internals.
- Normalized empty condition/allergy entries before presentation and added regression coverage for both populated and empty states.

## 4.8.0 — 2026-08-31

- Moved OTP verification from every login to one-time account sign-up and Forgot Password recovery.
- Added persistent `email_verified_at` account state with a safe migration that preserves all existing accounts as verified.
- Added current Streamlit Cloud `stColumn` compatibility throughout landing, authentication and portal responsive rules.
- Added screen-width containment, flexible laptop padding, stacked mobile forms, responsive media and scroll-safe tables.

## 4.7.1 — 2026-08-31

- Added compatibility for both current Streamlit Cloud and local column identifiers so the authentication board remains compact and centered on desktop and mobile.
- Updated the documented live application address to the public `nutripulse-ai.streamlit.app` URL.

## 4.7.0 — 2026-08-31

- Rebuilt authentication as a compact centered account board while keeping landing-page actions at the top right.
- Added verified Gmail password recovery with expiring codes and PBKDF2 password replacement.
- Added soft cyan, lilac, champagne and mint accents throughout authenticated role portals.
- Added animated star-wave layers to authentication and portal backgrounds with reduced-motion support.
- Increased portal captions, labels, card copy and sidebar navigation to normal readable sizes.

## 4.6.1 — 2026-08-31

- Moved landing/auth presentation into a fresh deployment module so Streamlit Cloud reloads it reliably.
- Added toolbar-safe top spacing to keep the navigation fully inside the application frame.
- Upgraded the capability banner to a continuous multicolour wave animation.
- Restored the intended Food Vision hero, floating cards, feature grid and responsive authentication layout.

## 4.6.0 — 2026-08-31

- Added a public, luxury dark landing page with top-right Log in and Sign up actions.
- Added animated nutrition feature cards, capability marquee and role-security proof section.
- Rebuilt authentication as a responsive dark split-screen experience inspired by the supplied references.
- Preserved Gmail verification, private Administrator setup, Dietitian approval and role-separated portals.
- Added reduced-motion accessibility and dedicated mobile layouts for the landing and authentication views.

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
