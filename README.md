<p align="center">
  <img src="assets/nutripulse_hero.jpg" alt="NutriPulse AI nutrition intelligence platform" width="100%">
</p>

<h1 align="center">NutriPulse AI v4.6.1</h1>

<p align="center">
  <strong>AI-assisted nutrition intelligence, clinical collaboration and longitudinal diet-plan monitoring.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/Streamlit-Application-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit application">
  <img src="https://img.shields.io/badge/FastAPI-REST_API-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Release-v4.6.1-6A5ACD" alt="Release v4.6.1">
  <img src="https://img.shields.io/badge/Source_rows-76%2C920-16423C" alt="76,920 audited source rows">
</p>

<p align="center">
  <a href="https://nutripulse-3765cfgbezsflrv6ht4kaa.streamlit.app/">
    <img src="https://img.shields.io/badge/Open-Live_App-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Open the NutriPulse AI live app">
  </a>
  <a href="https://github.com/abdmughal0912-sudo/Nutripulse/archive/refs/heads/main.zip">
    <img src="https://img.shields.io/badge/Download-NutriPulse_v4.6.1-2EA44F?style=for-the-badge&logo=github&logoColor=white" alt="Download NutriPulse v4.6.1">
  </a>
  <a href="RELEASE_NOTES.md">
    <img src="https://img.shields.io/badge/View-Release_Notes-1F6FEB?style=for-the-badge" alt="View release notes">
  </a>
</p>

NutriPulse is a nutrition intelligence platform built with Streamlit, FastAPI, persistent PostgreSQL or local SQLite, Pandas, Plotly, ONNX/OpenCV inference, bundled RapidOCR, and a portable pure-Python food-quality classifier. Version 4.6.1 introduces a reliably loaded luxury public landing page, multicolour wave advertising and responsive dark split-screen authentication while preserving reboot-safe cloud accounts, Gmail verification, automatic day/week progression, analytics and separated Customer, Dietitian and Administrator workspaces. Aggregate lineage in the public repository audits all 76,920 supplied source rows without publishing person-level benchmark rows.

**Live application:** [NutriPulse AI — Nutrition Analyzer & Dietitian Platform](https://nutripulse-3765cfgbezsflrv6ht4kaa.streamlit.app/)

## Product experience

<table>
  <tr>
    <td width="33%" align="center">
      <img src="assets/food_vision_luxury.jpg" alt="Food Vision and nutrition diary" width="100%"><br>
      <strong>Food Vision & Diary</strong><br>
      Image-assisted food recognition with confirmation, nutrition matching and diary logging.
    </td>
    <td width="33%" align="center">
      <img src="assets/lab_nutrition.jpg" alt="Laboratory nutrition intelligence" width="100%"><br>
      <strong>Laboratory Intelligence</strong><br>
      OCR/PDF extraction, verification and safety-gated nutrition planning.
    </td>
    <td width="33%" align="center">
      <img src="assets/web_insights.jpg" alt="Evidence and public API extraction" width="100%"><br>
      <strong>Evidence & Public APIs</strong><br>
      Curated evidence plus safe extraction from public HTML, JSON, XML, CSV and text resources.
    </td>
  </tr>
</table>

## Download the release package

GitHub generates a clean ZIP package directly from the secured <code>main</code> branch:

**[Download NutriPulse AI v4.6.1](https://github.com/abdmughal0912-sudo/Nutripulse/archive/refs/heads/main.zip)**

The package includes the application, API, audited public data indexes, portable classifier, Food Vision model, launchers, documentation and tests. It excludes passwords, API keys, runtime databases, Customer records, <code>.env</code>, Streamlit secrets and the private person-level row registry.

## Fastest Windows start

1. Install Python 3.12 and select **Add Python to PATH**.
2. Extract the complete ZIP.
3. Double-click `START_NUTRIPULSE.bat` in the outer folder, or open `NutriPulse_App` and run `START_ALL.bat`.
4. Open <http://127.0.0.1:8501>.
5. Create the first Administrator, then approve Dietitian applications and assign Customers.

Before starting, create a long private value for `NUTRIPULSE_ADMIN_SETUP_CODE` in your environment or `.streamlit/secrets.toml`. Administrator registration remains disabled when the value is missing. Never commit the real value. If startup fails, open `NUTRIPULSE_STARTUP_LOG.txt` inside `NutriPulse_App` for the exact diagnostic.

## Email verification at sign-in

After the password is accepted, every Customer, Dietitian and Administrator must enter a six-digit code delivered to the account's registered email. New registrations require a valid email; older accounts without one complete a one-time verified-email enrollment.

For Gmail, use a dedicated sending account with Google 2-Step Verification and a Google App Password. Add the following privately in Streamlit **App settings → Secrets**:

```toml
NUTRIPULSE_SMTP_HOST = "smtp.gmail.com"
NUTRIPULSE_SMTP_PORT = "587"
NUTRIPULSE_SMTP_USERNAME = "your-sender@gmail.com"
NUTRIPULSE_SMTP_PASSWORD = "your-16-character-app-password"
NUTRIPULSE_SMTP_SENDER_EMAIL = "your-sender@gmail.com"
NUTRIPULSE_SMTP_SENDER_NAME = "NutriPulse AI"
```

Never use or commit the normal Gmail password. See `.streamlit/secrets.toml.example` and `DEPLOYMENT.md` for the complete configuration.

## Persistent accounts on Streamlit Community Cloud

Streamlit Community Cloud can replace the app's local filesystem whenever the app reboots or redeploys. A local SQLite file therefore must not be used for hosted Customer accounts. Create a managed PostgreSQL database (Neon, Supabase, or another PostgreSQL provider), copy its private connection string, and add this root-level secret in Streamlit **App settings → Secrets**:

```toml
NUTRIPULSE_DATABASE_URL = "postgresql://user:password@host/database?sslmode=require"
```

Save the secret and reboot the app. Administrator Governance must show **PostgreSQL**, **Managed cloud database**, and **Cloud reboot safe: Yes** before real accounts are created. Keep the URL private because it contains the database password. Local Windows installations continue to use `data/nutripulse.db` automatically.

## VS Code

Open the exact `NutriPulse_App` folder. The Explorer should show `app.py`, `api.py`, `requirements.txt`, `src`, `data`, and `models`. Then run:

```powershell
.\START_ALL.bat
```

The launcher selects Python 3.12/3.11, creates `.venv`, installs requirements, starts FastAPI in a second terminal, and starts Streamlit.

## Role-based workspaces

### Customer

- Private login and account-isolated persistent records.
- Daily Overview with alerts, meal schedule, past records, and future plan graph.
- Personal profile and laboratory intelligence.
- Bundled image/scanned-PDF OCR, PDF table extraction, 38 recognized laboratory tests, additional-test capture, and a fresh verification table for every report.
- Sequential diet-plan cycles: completing a day opens the next day; completing Day 7 records the finished week and creates the next week automatically.
- Live 60-second meal reminder watcher while the app is open.
- Food Vision from uploads or direct public JPG/PNG/WebP URLs.
- Database-linked calories, protein, carbohydrates, fat, fibre, sugar, sodium, health score, confidence, and limitations.
- Confirmed food diary and removal workflow.
- Daily and week-by-week completion analytics, completed-week history, weight, hydration, waist, and adherence.
- Customer Care Team for Dietitian connections, questionnaires, and secure messages.
- NutriGuide built-in assistant plus optional consent-gated external API adapter.

### Dietitian

- Dedicated professional application with registration/license details.
- Inactive-until-approved account status and automatic clinical-portal routing after login.
- Assigned-caseload dashboard and customer selector; no Customer pages in Dietitian navigation.
- Customer vitals, BMI, conditions, allergies, alert feed, weight trend, daily completion and week-by-week adherence.
- Complete food diary review with daily calorie and macro totals.
- Laboratory report analysis, safety-gated Dietitian plan generation and full plan history.
- Formal plan reviews with Dietitian, Doctor, Renal Dietitian or Diabetes Educator acting role.
- Permanently Customer-hidden private clinical notes.
- Customer-visible nutrition prescriptions, questions, recommendations and questionnaire threads.

### Administrator

- First-run protected setup and normal secure sign-in afterward.
- Approve or reject pending Dietitian applications.
- Assign Customers to approved Dietitians.
- Full-customer override for clinical review.
- Account directory, caseload audit, aggregate 76,920-row dataset lineage and model governance.

## Nine-dataset integration

The build pipeline uses each supplied file according to its meaning:

| Dataset group | Use |
| --- | --- |
| Six food/nutrition tables | Normalized into `data/master_food_index.csv` for search, matching, Food Vision nutrition estimates, and classifier training |
| Two allergen/restriction tables | Normalized into `data/food_safety_registry.csv`; never treated as nutrition labels |
| One person-level intake table | Summarized in `data/intake_benchmarks.json`; never treated as a food record |

The current build audits exactly 76,920 supplied rows: 70,920 food/product-related source rows and 6,000 person-level benchmarks. Of these, 62,591 are nutrition-classifier candidates; validation and deduplication produce 47,152 nutrition-ready unique records. The 8,329 dedicated safety-source rows remain in the allergen/restriction layer. Aggregate lineage, hashes, counts and model metrics are recorded in `data/dataset_manifest.json`. The row-level `data/source_record_registry.csv` is generated locally but intentionally excluded from the public repository because it includes person-level benchmark lineage.

The offline build script is:

```bash
python scripts/build_unified_data.py --source-dir PATH_TO_NINE_CSVS --project-dir .
```

It requires scikit-learn only during the offline model build. The deployed application does not import SciPy or scikit-learn.

## Portable classifier

`models/nutrition_quality_portable.json` is a serialized Random Forest evaluated through `src/portable_classifier.py` using the Python standard library. This directly avoids the Windows Application Control errors previously caused by SciPy DLLs.

Current held-out metrics are stored in `models/nutrition_quality_model_card.json` and displayed in the application. Classification is educational; model confidence is not clinical certainty.

## Food Vision and internet images

- Local upload: Food Vision & Diary → **Upload image**.
- Public URL: Food Vision & Diary → **Public image URL**.
- API upload: `POST /api/v1/vision/analyze`.
- API URL analysis: `POST /api/v1/vision/analyze-url`.
- API URL analysis + diary logging: `POST /api/v1/diary/vision-url`.
- Optional `dish_hint` accepts a confirmed regional or out-of-class dish name through the analysis APIs.

Remote-image checks reject private/local addresses, redirects to private networks, unsupported types, oversized files, and invalid image bytes. The local model contains 101 classes. If its confidence or top-class margin is insufficient, NutriPulse stops before attaching calories and asks for the actual dish name. Confirmed regional foods such as biryani are reranked against the complete nutrition database. Nutrition comes from the closest database match and selected portion—not directly from pixels—so the user must confirm the dish, recipe, and portion. Food Vision automatically falls back to OpenCV DNN if Windows blocks the optional ONNX Runtime DLL.

## Evidence and public API extraction

Evidence Web & API supports curated evidence, public HTML pages, and public GET APIs that return JSON, XML, CSV or text. Optional bearer tokens and API-key headers remain session-only. Credentials inside URLs, private/local destinations, unsafe redirects, non-standard ports and responses larger than 1.5 MB are blocked. If a curated official site returns HTTP 403/429, the app displays a clearly labeled bundled, attributed summary rather than claiming that live extraction succeeded.

## FastAPI

Swagger: <http://127.0.0.1:8000/docs>

Important endpoints:

- `GET /health`
- `GET /api/v1/foods/search`
- `POST /api/v1/classifier/predict`
- `POST /api/v1/labs/analyze`
- `POST /api/v1/diet/plan`
- `POST /api/v1/vision/predict`
- `POST /api/v1/vision/analyze`
- `POST /api/v1/vision/analyze-url`
- `POST /api/v1/diary/vision-url`
- `GET /api/v1/diary`
- `POST /api/v1/assistant/ask`
- `GET /api/v1/schedule`
- `POST /api/v1/schedule/{meal_id}/status`
- `POST /api/v1/alerts/evaluate`
- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{alert_id}/acknowledge`
- `POST /api/v1/web/scrape`
- `POST /api/v1/web/extract`

Set `NUTRIPULSE_API_KEY` in production. Clients send it as `X-API-Key`.

## Nutrition Assistant API adapter

NutriGuide works offline by default. To connect an approved external assistant service:

```text
NUTRIPULSE_ASSISTANT_API_URL=https://approved-service.example/ask
NUTRIPULSE_ASSISTANT_API_KEY=replace-with-secret
```

External transfer is disabled until the Customer explicitly selects the consent checkbox and toggle. The adapter sends a minimized nutrition context and preserves no-diagnosis/no-prescribing boundaries.

## Tests

```bash
python -m unittest discover -s tests -v
python scripts/smoke_test.py
python scripts/ui_smoke_test.py
```

The UI test renders every Customer, Dietitian and Administrator page. The smoke test checks Food Vision inference, the portable classifier, dataset integrity, alerts, plans, PDF/CSV/JSON exports and database persistence.

## GitHub

This source tree is safe to publish after configuring repository visibility for your privacy needs. Runtime databases, virtual environments, local secrets, Streamlit secrets and generated exports are excluded by `.gitignore`. The bundled Food Vision model and audited data indexes are below GitHub's normal 100 MB per-file limit, so Git LFS is not required.

The workflow in `.github/workflows/ci.yml` validates Python 3.12 imports, all automated tests, model/data integrity and every role-based Streamlit page on each push to `main` and on every pull request.

GitHub stores and validates the source code; it does not run this Streamlit/FastAPI application as GitHub Pages. Use a Python-capable host and follow `DEPLOYMENT.md` for an internet-facing deployment. Never commit a real `.env` file, Administrator setup code, API key or Customer database.

## Medical and privacy scope

NutriPulse is decision support and education, not diagnosis, emergency care, or medical prescribing. Nutrition prescriptions must remain within the professional's jurisdictional scope. OCR values require human verification. Food images cannot verify ingredients, allergens, cross-contact, or exact portions. Production deployment requires clinical validation, a private Administrator setup code, API protection, TLS, encrypted backups, consent procedures, audit/retention rules and jurisdiction-specific privacy review.
