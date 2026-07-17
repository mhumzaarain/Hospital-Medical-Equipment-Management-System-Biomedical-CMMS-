# Biomedical CMMS — Design Specification

**Date:** 2026-07-17
**Status:** Approved design, pre-implementation
**Context:** Portfolio/demo-first project; production hardening deferred where noted.

A server-rendered Django web application for hospitals to track medical equipment
and manage malfunction complaints and repairs, with a small local-LLM layer for
narrative reporting and risk analysis.

---

## 1. Tech stack (fixed)

| Concern | Choice |
|---|---|
| Backend | Django (server-rendered templates; no DRF/SPA) |
| Frontend | Django templates + HTMX + Alpine.js + Chart.js + Tailwind CSS (standalone CLI binary — no Node.js) |
| Database | PostgreSQL, standard image (JSONB where sensible; **no pgvector**) |
| Task queue | Procrastinate (Postgres as broker — no Redis) |
| LLM | Local Ollama, one chat model, configurable via env var (default `llama3.1:8b`; smaller model acceptable for CPU-only demo). No external AI APIs; data never leaves the server. |
| Auth | Django session auth with role field on the user (no JWT) |
| PDF | WeasyPrint |
| Deployment | Docker Compose: web (Gunicorn + Nginx), postgres, procrastinate worker, ollama. All config via environment variables (hospital name, logo, SMTP, model name, timezone). |

## 2. Roles and permissions

Three roles stored as a field on a custom `User` model. Enforced in **two layers**:
view-level mixins (`RoleRequiredMixin`) for page access, and re-checked inside every
service function so the rules hold from admin, shell, and scripts too.

| Capability | Staff | Engineer | Admin |
|---|---|---|---|
| Lodge complaint; view own complaints | ✅ | ✅ | ✅ |
| View equipment registry (read-only) | ✅ | ✅ | ✅ |
| Add/edit equipment; CSV import | — | ✅ | ✅ |
| Open/work/close WorkOrders; add remarks; transition statuses | — | ✅ | ✅ |
| Close complaints (incl. as duplicate) | — | ✅ | ✅ |
| Condemn equipment | — | ✅ | ✅ |
| Dashboard and reports | — | ✅ | ✅ |
| Manage users, departments (stock Django admin) | — | — | ✅ |

User management happens in the stock Django admin in the MVP (no custom UI).
`User` fields: standard auth fields + `employee_id` (unique), `role`
(staff / engineer / admin), optional informational `department` FK.
Departments do **not** scope visibility — they are a reporting attribute only.

## 3. Django app breakdown

| App | Responsibility |
|---|---|
| `accounts` | Custom `User`, login/logout, role mixins/decorators |
| `core` | `AuditLog`, shared model utilities, `seed_demo` management command |
| `equipment` | `Department`, `Equipment`, `StatusEvent`, status-transition service, registry UI, CSV importer |
| `maintenance` | `Complaint`, `WorkOrder`, `Remark`, complaint/work-order services and UI, complaint queue |
| `ai` | Ollama client, prompts, all LLM Procrastinate tasks (`RiskAssessment`, `DeviceChatMessage`) |
| `reports` | Dashboard (Chart.js), monthly PDF report generation |

`ai` isolates everything Ollama-dependent: the system is fully functional with
Ollama down or absent (Phase 1 has zero AI dependencies). `reports` only reads
other apps' models. Every app keeps a `services.py`; views stay thin and **all
state changes go through services** (transitions, closures, cascades, audit writes).

## 4. Data model

### 4.1 equipment.Department
`name`, `location`. Referenced by Equipment with `on_delete=PROTECT`.

### 4.2 equipment.Equipment
- Identity: `name`, `manufacturer`, `vendor`, `model_number`, `serial_number` (unique)
- Classification: `department` FK, `is_critical_asset` (boolean — engineer-set flag
  for the few high-value machines like MRI/CT/Angiography whose downtime is tracked)
- Dates: `purchase_date`, `installation_date`
- Lifecycle: `status` (`working` / `in_repair` / `condemned`) — a **denormalized
  cache** of the latest StatusEvent, always written in the same transaction;
  `condemned_at`, `condemned_location` (physical location of the condemned unit)
- `extra` JSONB — overflow fields from CSV import

**Equipment can never be deleted.** No delete views; admin delete action disabled;
`Model.delete()` raises. Lifecycle ends at status `condemned` (terminal).

### 4.3 equipment.StatusEvent (append-only)
`equipment` FK, `old_status`, `new_status`, `actor` FK, `created_at`, `remark`,
`work_order` FK (nullable). Insert-only: `save()` refuses updates; no admin editing.
This typed event stream is the source of truth for lifecycle history and downtime.

**Status machine** — single service choke point
`equipment.services.transition_status(equipment, new_status, actor, remark, work_order=None)`:
- Allowed transitions: `working → in_repair`, `in_repair → working`,
  `working|in_repair → condemned`. `condemned` is terminal.
- Validates actor role, then atomically: updates the cached `status`, inserts the
  `StatusEvent`, writes the `AuditLog` entry.
- Nothing else ever writes `Equipment.status`.

### 4.4 maintenance.Complaint
`equipment` FK, `reporter` FK (auto-stamped from the logged-in user; the user's
name and employee_id display with it), `description` (free text), `created_at`,
`status` (`open` / `attached` / `closed`), `work_order` FK (nullable),
`close_reason` (`resolved` / `duplicate` / `no_fault`), `duplicate_of` FK-self
(nullable), `close_note`, `closed_by`, `closed_at`.

Complaint form: staff **search-and-select** the device (HTMX autocomplete over
serial number / name / model); manufacturer, model, department autofill from the
registry. Hard FK — no free-text device entry. QR-code entry is out of scope
(deferred beyond Phase 3).

**Duplicate handling is manual workflow, not AI:**
1. If the device is `in_repair`, new complaints are **blocked** at the service
   layer (form also hides the device): *"already under repair (Work Order #N)."*
2. Before a repair starts, multiple complaints for one device are allowed. An
   engineer closes an extra complaint with `close_reason=duplicate`, linking
   `duplicate_of` and/or writing a `close_note`
   (e.g. "already reported by Nurse XYZ, complaint #482").
3. Complaints may also be closed `no_fault` (false alarm) or `resolved`
   (via the work-order cascade).

### 4.5 maintenance.WorkOrder
`equipment` FK, `status` (`open` / `in_progress` / `completed` / `cancelled`),
`opened_by`, `opened_at`, `repair_started_at`, `repair_completed_at`,
`closed_by`, `closed_at`, `outcome` (`repaired` / `condemned`).

- Complaints attach N:1 to a WorkOrder; a WorkOrder may also exist with zero
  complaints (engineer-initiated, e.g. found during inspection).
- **At most one non-closed WorkOrder per device** (partial unique index).
- Starting the repair sets `repair_started_at` and transitions the equipment to
  `in_repair`. Completing sets `repair_completed_at`, transitions equipment back
  to `working` (or the condemnation path), and closes attached complaints with
  `close_reason=resolved` — one transaction.
- Cancelling (false alarm): attached complaints close with `close_reason=no_fault`; equipment
  returns to / stays `working`.

### 4.6 maintenance.Remark (append-only)
`work_order` FK, `author`, `text`, `kind` (`note` / `delay` / `system`),
`created_at`. Insert-only.

There is **no SLA system** (no policies, deadlines, breach detection, or
escalation). The `delay` kind exists so an engineer can *voluntarily* record
why a repair is taking long ("waiting for vendor part", "holidays"); delayed
repairs so annotated are listed in reports. Nothing enforces or times this.

### 4.7 ai.RiskAssessment
`equipment` FK, `score` (0–100), `factors` JSONB (the SQL-computed inputs:
repair count, recency, repeat-fault indicators), `narrative` (LLM text),
`generated_at`. New row per run — history preserved.

### 4.8 ai.DeviceChatMessage (Phase 3)
`equipment` FK, `user` FK, `role` (`user` / `assistant`), `content`, `created_at`.

### 4.9 core.AuditLog (append-only)
`actor`, `verb`, `content_type` / `object_id`, `changes` JSONB, `created_at`.

**Audit architecture (hybrid):** equipment status transitions get the typed
`StatusEvent` table (they drive analytics); every other significant mutation
(equipment edits, complaint closures, work-order actions, remark additions)
is recorded by the service layer into the generic `AuditLog`. Both are
append-only; nothing in the system hard-deletes domain data.

## 5. Complaint lifecycle (end to end)

1. Staff member logs in, searches the device, submits a free-text description.
   Complaint is stamped with their account.
2. If the device already has an open WorkOrder → complaint auto-attaches
   (`status=attached`; engineers see "+1 report"). If the device is `in_repair`
   → submission is blocked. Otherwise the complaint enters the queue (`open`).
3. Engineers watch the queue (HTMX polling, newest first). They may close
   duplicates/no-faults manually, or open a WorkOrder from a complaint
   (attaching any sibling open complaints for the same device).
4. Engineer starts repair → `repair_started_at`, equipment → `in_repair`.
5. Engineer completes → `repair_completed_at`, equipment → `working`,
   attached complaints → closed (`resolved`). Or the path ends in condemnation (§6).

## 6. Condemnation cascade

Condemning a device (engineer or admin, with mandatory remark, condemnation
date, and physical location of the unit) runs in one transaction:
- transition to `condemned` (StatusEvent recorded),
- auto-complete any open WorkOrder with `outcome=condemned`,
- close all attached/open complaints with a system note "device condemned",
- block all future complaints and transitions for the device.

The record and its full history remain forever.

## 7. Metrics and reporting

**No MTTR anywhere** (rejected: a single parts-delay or holiday outlier
distorts a mean into a false story). **No SLA metrics.**

- **Downtime — critical assets only.** Computed per device from timestamps:
  complaint received (or work-order opened, if engineer-initiated) →
  `repair_completed_at`. Only devices with `is_critical_asset=true` are included;
  aggregated per department and per device. A repair spanning a month boundary
  contributes its hours to each month proportionally.
- **Dashboard (Chart.js):** critical-asset downtime, complaints per department,
  most-complained devices, repairs completed count, currently open work orders,
  and repairs carrying `delay` remarks with their reasons.
- **Monthly management report:** the same aggregates for the month, computed in
  SQL, plus an LLM-written narrative summary; rendered to PDF (WeasyPrint),
  stored on disk, downloadable; generated monthly by schedule and on demand.

**Design rule for all AI features: numbers come from SQL, words come from the
LLM.** The LLM never computes metrics and never changes workflow state; every
LLM output lands in a nullable field the UI treats as optional enrichment.

## 8. Procrastinate task inventory

| Task | Trigger | Description |
|---|---|---|
| `compute_risk_scores` | weekly (periodic) | SQL stats per device (repair frequency, recency, repeat faults) → deterministic score + LLM narrative → `RiskAssessment` row |
| `generate_monthly_report` | monthly (periodic) + on-demand | Aggregate month's metrics in SQL → LLM narrative → PDF |
| `answer_device_chat` | on chat message (Phase 3) | Load the device's **full** complaint/work-order/remark/status history into the prompt (context stuffing — no RAG/embeddings; per-device history is small) → LLM answer; UI polls via HTMX |
| `nightly_backup` | daily (periodic) | `pg_dump` to a mounted volume; prune old dumps |

All LLM tasks: retry with backoff; on persistent failure the feature silently
shows "not available yet" — core workflow never blocks on the LLM.

## 9. Explicitly out of scope / removed

- SLA policies, deadlines, breach detection, escalation emails — removed.
- LLM complaint triage — removed (manual queue ordering: newest first).
- AI duplicate detection, embeddings, pgvector — removed (manual duplicate workflow, §4.4).
- MTTR — removed. (If a speed metric is ever wanted: median time-to-repair.)
- QR-code stickers — deferred beyond Phase 3.
- Websockets — HTMX polling only.
- Custom user-management UI — Django admin suffices.

## 10. Phasing

**Phase 1 — Core CMMS (zero AI):** accounts + roles; equipment registry with
StatusEvent machine and condemnation cascade; complaint → WorkOrder workflow
with manual duplicate rules; remarks; AuditLog; HTMX complaint queue; dashboard
(critical-asset downtime, complaints per dept, most-complained devices);
`seed_demo` command; Docker Compose (web, postgres, worker); Tailwind base UI.
*A complete, honest CMMS on its own.*

**Phase 2 — AI + adoption:** Ollama service + client; `compute_risk_scores`;
`generate_monthly_report` with PDF; CSV/Excel importer (dry-run preview →
confirm; errors reported per row; nonstandard columns land in `extra` JSONB).

**Phase 3 — Polish:** device-history chat; nightly backup task; SMTP email
notifications; demo-mode refinements.

## 11. Testing

pytest + pytest-django. Priority order:
1. **Service-layer rules** (the heart): status machine transitions incl. illegal
   ones, one-open-work-order constraint, in-repair complaint blocking,
   condemnation cascade, append-only enforcement, role checks in services.
2. Downtime aggregation math (incl. month-boundary proration).
3. View access control per role.
4. AI tasks tested with a faked Ollama client (no model in CI).

## 12. Repository structure

```
biomedical-cmms/
├── docker-compose.yml            # web, postgres, worker, ollama
├── Dockerfile
├── .env.example                  # HOSPITAL_NAME, LOGO, SMTP_*, OLLAMA_MODEL, TIME_ZONE …
├── manage.py
├── pyproject.toml
├── config/
│   ├── settings/ (base.py, dev.py, prod.py)
│   ├── urls.py
│   └── procrastinate.py          # app + periodic task registration
├── apps/
│   ├── accounts/
│   ├── core/
│   ├── equipment/                # models / services / views / importer
│   ├── maintenance/              # models / services / views
│   ├── ai/                       # client.py, tasks.py, prompts/
│   └── reports/
├── templates/                    # base.html, per-app dirs, partials/ for HTMX
├── static/                       # css (Tailwind CLI output), vendored js
├── docs/superpowers/specs/
└── tests/                        # per-app, pytest-django
```

All timestamps stored UTC; displayed in the hospital's configured timezone.
