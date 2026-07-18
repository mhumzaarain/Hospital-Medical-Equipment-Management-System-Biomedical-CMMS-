# Deferred follow-ups

Items intentionally deferred out of Phase 1. None block the Phase 1 merge; the
production-hardening item MUST be addressed before any real (internet- or
network-exposed) hospital deployment.

## Before any production deployment — security hardening

Phase 1 runs the demo over plain HTTP (docker-compose, nginx on port 8080), so
secure-transport settings are intentionally left off to keep the demo working.
Before exposing the app to real users, add HTTPS and enable these in
`config/settings/prod.py` (recommended: gate them behind an `ENABLE_HTTPS`
environment flag so the HTTP demo still works when the flag is off):

- `SESSION_COOKIE_SECURE = True` — only send the session cookie over HTTPS.
- `CSRF_COOKIE_SECURE = True` — only send the CSRF cookie over HTTPS.
- `SECURE_SSL_REDIRECT = True` — redirect HTTP requests to HTTPS.
- `SECURE_HSTS_SECONDS` (+ `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`)
  — tell browsers to always use HTTPS for this site.
- Guard `SECRET_KEY`: in prod, refuse to start if it is still the insecure
  default (`base.py` falls back to `"dev-insecure-key"` when the env var is
  unset). Raise `ImproperlyConfigured` instead of running insecurely.

Requires TLS termination in front of nginx (or in nginx itself) in the target
environment.

## Minor code-quality items (non-blocking, from the final review)

- `workorder_remark` view silently drops an invalid POST (no error message
  shown). Minor UX; the remark form has a single required field.
- `complaint_new` discards the user's entered equipment/description if lodging
  is blocked (redirects instead of re-rendering the bound form). Minor UX.
- `close_complaint` re-runs its role check once per complaint inside the
  complete/cancel cascade loops — harmless redundancy.
- Empty-query equipment search ignores `exclude_unavailable` (dead branch;
  an empty query already returns no rows).
- `test_employee_id_unique` catches a bare `Exception` (could be tightened to
  `IntegrityError`). Add direct negative-role tests for the equipment
  edit/condemn views (they share the mixin proven by the create-view test).

## Phase 2 / Phase 3 (per the spec, out of Phase 1 scope)

- Phase 2: Ollama client, weekly risk scoring, monthly PDF report, CSV/Excel importer.
- Phase 3: device-history chat (RAG-free context stuffing), nightly pg_dump
  backup task, SMTP email notifications.
