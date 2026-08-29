# NutriPulse v4.3 deployment

## Local Windows deployment

Use Python 3.12 or 3.11. Extract the project, open `NutriPulse_App`, and run `START_ALL.bat`. The application does not require SciPy or scikit-learn at runtime.

## Required production secrets

```text
NUTRIPULSE_ADMIN_SETUP_CODE=<long private first-administrator setup code>
NUTRIPULSE_API_KEY=<long independent API secret>
NUTRIPULSE_CORS_ORIGINS=https://your-frontend.example
NUTRIPULSE_UTC_OFFSET_HOURS=5
```

Optional assistant adapter:

```text
NUTRIPULSE_ASSISTANT_API_URL=https://approved-service.example/ask
NUTRIPULSE_ASSISTANT_API_KEY=<secret>
```

The row-level `data/source_record_registry.csv` is private build output and is excluded from the public repository. Generate it only in an authorized environment from the original nine source files. The public `data/dataset_manifest.json` retains aggregate counts and model lineage.

Optional paths:

| Variable | Purpose | Default |
| --- | --- | --- |
| `NUTRIPULSE_DATABASE_PATH` | SQLite database | `data/nutripulse.db` |
| `NUTRIPULSE_FOOD_DATA_PATH` | Master food CSV | `data/master_food_index.csv` |
| `NUTRIPULSE_DATA_DIR` | Data directory | `data` |
| `NUTRIPULSE_MODEL_DIR` | Model directory | `models` |
| `NUTRIPULSE_ASSET_DIR` | Asset directory | `assets` |
| `NUTRIPULSE_API_URL` | API URL shown by Streamlit | `http://127.0.0.1:8000` |
| `NUTRIPULSE_SCRAPER_DOMAINS` | Extra allowlisted evidence domains | empty |

## Docker Compose

1. Copy `.env.example` to `.env`.
2. Replace every placeholder.
3. Run:

```bash
docker compose up --build -d
```

Open:

- Streamlit: <http://localhost:8501>
- FastAPI: <http://localhost:8000/docs>

The named volume stores the SQLite database. Back it up before upgrades.

## Production checklist

- Put both services behind HTTPS and an authenticated reverse proxy.
- Use a private Administrator setup code, remove first-run bootstrap exposure after setup, and approve each Dietitian through Administrator Governance.
- Set the API key and strict CORS origins.
- Restrict filesystem and database access to the application identity.
- Encrypt backups and test restore procedures.
- Define customer consent, data-retention, correction, export, and deletion procedures.
- Validate laboratory thresholds, diet constraints, alert language, and escalation workflows with qualified local clinicians.
- Treat external assistant configuration as a separate processor/vendor review; keep it disabled until approved.
- Add centralized audit logging, rate limiting, monitoring, and incident response before real clinical use.
- Never treat Food Vision or the classifier as a diagnostic system.

## Upgrade from an earlier version

Copy `data/nutripulse.db` into the new `data` folder before first start. Database initialization is additive and preserves approval, administrator, clinical-note, prescription, typed-message, report-linkage and meal-completion history. Existing approved Dietitian accounts remain active. Legacy `default-profile` data remains in the database but is not automatically assigned to a new account; migrate it only with appropriate identity verification and consent.
