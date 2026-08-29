# NutriPulse AI v4.4 — Release Notes

![NutriPulse AI](assets/nutripulse_hero.jpg)

## Download

**[Download the secured NutriPulse v4.4 package](https://github.com/abdmughal0912-sudo/Nutripulse/archive/refs/heads/main.zip)**

## Release highlights

- Mandatory six-digit email verification after every successful password check.
- Ten-minute code expiry, five-attempt limit and a 60-second resend cooldown.
- One-time verified-email enrollment for existing accounts without an email.
- Separate Customer, Dietitian and Administrator workspaces.
- Administrator approval for Dietitian applications and controlled caseload assignment.
- Persistent day-to-day meal progression and automatic Week 1 → Week 2 advancement.
- Daily, weekly, adherence, weight, hydration and meal-completion analytics.
- Food Vision with low-confidence confirmation and regional-food database reranking.
- Laboratory report OCR/PDF extraction with human verification and nutrition safety gates.
- Evidence and public GET API extraction for HTML, JSON, XML, CSV and text.
- Secure clinical notes, formal plan reviews, prescriptions, questionnaires and messaging.
- Streamlit application plus FastAPI endpoints and Swagger documentation.
- Windows-safe portable nutrition classifier with optional ONNX/OpenCV Food Vision runtime.

## Data and model summary

| Item | Release value |
| --- | ---: |
| Supplied source rows audited | 76,920 |
| Food/product-related source rows | 70,920 |
| Classifier-ready unique food profiles | 47,152 |
| Dedicated safety-source rows | 8,329 |
| Population benchmark rows summarized | 6,000 |

The public package contains aggregate lineage and model-ready artifacts. The person-level row registry is intentionally excluded from GitHub and must be generated only in an authorized local environment.

## Windows requirements

- Windows 10 or 11
- Python 3.12 recommended
- Internet access during the first dependency installation
- Microsoft Visual C++ Redistributable recommended for ONNX Runtime

## Secure first Administrator setup

Open PowerShell in the extracted project folder:

~~~powershell
$adminCode = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$env:NUTRIPULSE_ADMIN_SETUP_CODE = $adminCode
Write-Host "Administrator setup code: $adminCode"
.\START_ALL.bat
~~~

Enter the displayed code only during first Administrator registration. Never commit it to GitHub.

## Validation

The repository includes automated unit/API tests, runtime checks, model/data smoke tests and role-based UI rendering tests under <code>.github/workflows/ci.yml</code>.

## Important scope

NutriPulse provides nutrition decision support and education. It does not replace medical diagnosis, emergency care or licensed clinical judgment. OCR results, food-image predictions and generated plans require appropriate human verification.
