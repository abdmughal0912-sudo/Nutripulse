# NutriPulse production-readiness review

**Reviewed release:** 4.12.0  
**Review date:** 2026-09-11  
**Scope:** source code, account access, care workflows, persistence, API configuration and automated validation.

This release strengthens the existing application. It does not certify medical effectiveness, regulatory compliance or capacity for a particular number of users.

## Findings and implemented changes

| Observed gap | Implemented behavior | Verification |
| --- | --- | --- |
| Cached account sessions continued after access changes | Recheck active/verified/approved status, role and session version before portal work and during heartbeat checks | Revocation and changed-access tests |
| Password recovery left existing sessions active | Increase session version and clear live presence after the verified password changes | Password-change regression |
| Password sign-in had no shared attempt limit | Atomic eight-attempt budget per 15-minute window; email and username share the account budget | Concurrent-session and alias tests |
| API accepted calls when no key was configured | All /api/v1 endpoints return 503 without configuration and 401 for an invalid key | Read and mutation gate tests |
| Opening one thread marked every thread as read | Read-only listing and explicit receipts scoped to recipient, sender and displayed message IDs | Cross-thread, wrong-recipient and arrival-race tests |
| Care actions had no persistent workflow | Due dates, priorities, status views, pagination and ordered change history | Caseload, cancellation and stale-edit tests |
| Hidden audio widgets could overwrite saved preferences | Reload saved settings before rendering; callbacks retain values of hidden controls | Interactive multi-page test |
| Future meals lowered clinical adherence scores | Clinical dashboard uses the last seven days through today and sorts by alerts/overdue tasks | Role-page validation |
| API configuration health was unclear | Separate liveness/readiness probes, response request IDs and no-store headers | Header and sanitized-failure tests |

## Care workflow

Customers create personal tasks and update their own task status. Assigned Dietitians work within their active caseload. Administrators may manage customer tasks across the system. Customers may cancel self-created tasks; staff cancel assigned tasks. Completed and cancelled records remain stored.

Each status update checks the expected revision so an old screen cannot silently replace a newer update. Task history records the actor, status, time and ordered revision. Care Tasks provides search, Active, Due today, Overdue, Completed and All filters, and 20 records per page.

Care Inbox groups the signed-in account's conversations. Unread counts refresh every 60 seconds while the portal is open, with optional message chimes. The latest 50 messages appear in a conversation; earlier messages remain in storage. Explicit read receipts affect only displayed incoming messages. Historical messages remain available to their participants after reassignment, but new sending requires active, approved accounts and a currently authorized relationship.

## Account controls

Account & Security provides saved audio settings, the latest 100 account events and Sign out everywhere. Routine verified login remains email-or-username plus password; OTP stays limited to sign-up and recovery.

Sessions expire after one hour without interaction or twelve hours after sign-in. Background heartbeats do not extend the idle timer. Revoked access is enforced on the next action or heartbeat, rather than promising instantaneous disconnection. Password reset also clears the account's sign-in budget after successful ownership verification.

Account events store account ID, event type and UTC time. Passwords, OTP values and clinical message bodies are not included. This is account activity history, not a tamper-evident infrastructure audit log.

Voice choices persist in the configured database. Browser autoplay policies may still require a tap on a new device.

## Deployment and data

Initialization adds tables for tasks, task history, login budgets and account events, plus the account session-version column. It preserves existing accounts, laboratory reports, plans and meal records.

The SQLite-to-PostgreSQL importer now includes user preferences, care tasks, task history and account events. Transient presence and sign-in budgets are intentionally not migrated.

Every FastAPI /api/v1 request requires the configured NUTRIPULSE_API_KEY in X-API-Key. This is a trusted-server integration key, not per-customer authorization. Streamlit's built-in workflows call internal services directly and do not require a new API key.

Use /livez for process liveness, /readyz for database/API-key readiness and /health for model/data status. Readiness failures do not return connection strings or driver exception text.

## Validation and remaining rollout work

The release gate runs unit/API tests, runtime checks, Food Vision and nutrition-classifier smoke tests, and all Customer, Dietitian and Administrator pages. Stateful UI checks cover audio persistence, task updates, message receipts and session revocation. Tests use synthetic accounts and isolated databases.

Before a large or regulated clinical deployment:

1. Add per-client and per-user API authorization before exposing profile endpoints directly to end users. Keep the shared integration key on trusted servers.
2. Validate migrations on staging PostgreSQL and conduct an encrypted-backup restore drill for the chosen host.
3. Add gateway-wide traffic limits, centralized operational logs, retention rules and incident-response ownership. Per-account sign-in budgets do not stop distributed traffic attacks.
4. Measure concurrent workload, database connections and query latency; introduce database pagination and pooling where measurements justify it.
5. Complete screen-reader, real-device and browser-audio acceptance tests.
6. Obtain independent clinical validation of report interpretation, diet constraints and escalation flows. Continue human verification of extracted reports.

## Engineering references

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html): account-aware login throttling.
- [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html): access control, HTTPS and secret handling.
- [FastAPI request dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/): shared request guards.

These references informed implementation choices; their inclusion is not an external audit or certification.
