# NutriPulse v4.9.0 deployment

## Local Windows deployment

Use Python 3.12 or 3.11. Extract the project, open `NutriPulse_App`, and run `START_ALL.bat`. The application does not require SciPy or scikit-learn at runtime.

## Required production secrets

```text
NUTRIPULSE_ADMIN_SETUP_CODE=<long private first-administrator setup code>
NUTRIPULSE_DATABASE_URL=<private managed PostgreSQL connection string>
NUTRIPULSE_API_KEY=<long independent API secret>
NUTRIPULSE_CORS_ORIGINS=https://your-frontend.example
NUTRIPULSE_UTC_OFFSET_HOURS=5
NUTRIPULSE_SMTP_HOST=smtp.gmail.com
NUTRIPULSE_SMTP_PORT=587
NUTRIPULSE_SMTP_USERNAME=your-sender@gmail.com
NUTRIPULSE_SMTP_PASSWORD=<Google App Password, not the normal Gmail password>
NUTRIPULSE_SMTP_SENDER_EMAIL=your-sender@gmail.com
NUTRIPULSE_SMTP_SENDER_NAME=NutriPulse AI
```

Email verification is mandatory once during sign-up and for password recovery;
routine login uses the verified account's username and password. For Gmail SMTP, enable
Google 2-Step Verification on a dedicated sender account and generate an App
Password. Put it only in the hosting provider's secret manager. New accounts
must register a valid email. Existing accounts are marked verified during the
one-time schema migration so current users are not locked out.

Codes contain six digits, expire after 10 minutes, allow five attempts and can
be resent after 60 seconds. The app stores only a one-way digest of the active
code in the user's server-side Streamlit session. The same verified sender
delivers password-recovery codes; NutriPulse updates the PBKDF2 password hash
only after a valid recovery code is accepted.

Optional assistant adapter:

```text
NUTRIPULSE_ASSISTANT_API_URL=https://approved-service.example/ask
NUTRIPULSE_ASSISTANT_API_KEY=<secret>
```

The row-level `data/source_record_registry.csv` is private build output and is excluded from the public repository. Generate it only in an authorized environment from the original nine source files. The public `data/dataset_manifest.json` retains aggregate counts and model lineage.

## Streamlit Community Cloud persistent storage

The Streamlit app container and its local SQLite file can be replaced during a reboot or redeploy. Use a managed PostgreSQL database for hosted accounts:

1. Create a PostgreSQL database with Neon, Supabase, or another provider.
2. Copy its connection string and ensure TLS is enabled, commonly with `sslmode=require`.
3. Open Streamlit Community Cloud → your app → **App settings → Secrets**.
4. Add `NUTRIPULSE_DATABASE_URL = "postgresql://..."` at the root alongside the Administrator and SMTP secrets.
5. Save the secrets and reboot the app.
6. Sign in as Administrator and confirm **Cloud reboot safe: Yes** in Administrator Governance.
7. Create the Administrator and user accounts once. Future reboots and GitHub redeploys reuse the same PostgreSQL records.

Never commit this URL. It contains database credentials. If records were already deleted from Streamlit's temporary SQLite file, they cannot be recovered without a private `nutripulse.db` backup.

Optional paths:

| Variable | Purpose | Default |
| --- | --- | --- |
| `NUTRIPULSE_DATABASE_URL` | Managed PostgreSQL database; required for ephemeral cloud hosts | empty (uses SQLite) |
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

To import a private SQLite backup into the configured PostgreSQL database, set `NUTRIPULSE_DATABASE_URL`, then run:

```bash
python scripts/migrate_sqlite_to_postgres.py /private/path/nutripulse.db
```

The importer uses primary-key conflict protection and does not overwrite existing PostgreSQL rows. Back up both databases first and handle all Customer data according to your privacy and consent requirements.
