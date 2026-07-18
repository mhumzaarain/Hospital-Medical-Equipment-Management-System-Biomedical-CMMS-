# Complaints-Resolved Metric + Staff Confirmation Loop — Design Specification

**Date:** 2026-07-18
**Status:** Approved design, pre-implementation
**Builds on:** Phase 1 (`docs/superpowers/specs/2026-07-17-biomedical-cmms-design.md`).
This is a self-contained follow-on feature ("Phase 2a"): its own spec → plan →
TDD implementation.

Two linked features:
1. A single, clickable **"Complaints resolved"** metric per engineer on the
   dashboard, with a drill-down showing which equipment and the engineer's
   remarks.
2. A **staff confirmation loop**: after an engineer completes a repair, the
   reporting staff member is asked "Is the machine functional now?" and must
   answer; the engineer is then notified of the answer.

Plus one visibility tightening decided during design (staff cannot view
work-order detail pages).

---

## 1. Decisions locked in during brainstorming

- **Credit attribution** for "complaints resolved": a complaint resolved by a
  completed **repair** credits **every participant** of that work order; a
  complaint closed as **duplicate** or **no-fault** credits the engineer who
  closed it (`closed_by`). A shared repair therefore credits multiple engineers
  (a "your contribution" stat, not a hospital-wide distinct total).
- **"Not functional" answer** → **notify the engineer only**. Nothing
  auto-changes; no auto-reopen. The engineer decides and, if needed, opens a
  fresh work order manually (equipment is already back to `working`).
- **Notifications** are **derived from state** — no notification table, no
  email/SMTP, no read/unread tracking. Same approach as the existing HTMX queue.
- **Staff answer enforcement**: a **persistent, non-blocking** prompt on
  *My Complaints*. It stays until answered; it never blocks the rest of the app;
  there is no auto-close of unanswered prompts.
- **Work-order visibility tightened**: work-order detail pages become
  engineer/admin-only; staff see work-order references as plain text, not links.

## 2. Confirmed visibility model (role → what they see)

| Capability | Staff | Engineer | Admin |
|---|:--:|:--:|:--:|
| Lodge complaints | ✅ | ✅ | ✅ |
| See complaints | ✅ own only | ✅ all (queue) | ✅ all |
| Confirm "is it functional?" on own resolved complaints | ✅ | ✅ | ✅ |
| View equipment registry (read-only) | ✅ | ✅ | ✅ |
| Add / edit / condemn equipment | — | ✅ | ✅ |
| Open / work / close work orders, remarks | — | ✅ | ✅ |
| **View work-order detail pages** | **—** | ✅ | ✅ |
| Dashboard & analytics (complaints resolved per engineer) | — | ✅ | ✅ |
| Engineer "complaints resolved" drill-down | — | ✅ | ✅ |
| "Recent staff confirmations" panel | — | ✅ | ✅ |
| Manage users (Django `/admin/`) | — | — | ✅ |

Staff see only their own complaints plus the read-only equipment registry (which
they need to search devices when lodging).

## 3. Data model

Add to **`maintenance.Complaint`** (one migration, no new tables):

- `functional_confirmation` — `CharField(choices, null=True, blank=True)`:
  `null` = pending/not-applicable, `"functional"`, `"not_functional"`.
  New TextChoices `FunctionalConfirmation(FUNCTIONAL="functional",
  NOT_FUNCTIONAL="not_functional")`.
- `confirmed_at` — `DateTimeField(null=True, blank=True)`.

**"Awaiting confirmation" is derived, not stored** — a complaint awaits
confirmation when: `status=closed` AND `close_reason=resolved` AND
`work_order.outcome=repaired` AND `functional_confirmation IS NULL`. (Duplicates,
false-alarms, and condemnations are never asked — there is no repaired machine
to confirm.)

`Complaint` remains no-delete (append-only audit discipline unchanged);
confirmation is a one-time state transition on the complaint, recorded in the
AuditLog.

## 4. Feature 1 — "Complaints resolved" metric + drill-down

### 4.1 Attribution helper (single source of truth)
`apps.reports.metrics.resolving_engineer_ids(complaint) -> set[int]`:
- if `complaint.work_order` exists and has participants → those participants' ids;
- else → `{complaint.closed_by_id}` (duplicate/no-fault manual closes).

### 4.2 Dashboard count
Replace the current two-column "Engineer activity" table (`Repairs worked on`,
`Duplicates / false alarms closed`) with a single **"Complaints resolved"**
count per engineer, over the same rolling 30-day window (by `closed_at`).

`per_engineer_resolved(window_start, window_end) -> list[dict]` returns
`{name, employee_id, user_id, resolved_count}`, computed by iterating resolved
complaints in the window (`status=closed`, `closed_at` in window) and crediting
each id from `resolving_engineer_ids`. A complaint counts as resolved when it is
a **dismissal** (`close_reason in {duplicate, no_fault}`) **or** a **genuine
repair** (`close_reason=resolved` AND its `work_order.outcome=repaired`).
Complaints auto-closed by **condemnation** (resolved but `outcome=condemned`, or
no work order) are **excluded** — condemning a device is not "resolving" a
complaint in the made-good sense; condemnation lives in the equipment status
history. Only engineers with a non-zero count appear, ordered by count
descending. Each count links to the drill-down.

### 4.3 Drill-down page
`GET /dashboard/engineer/<user_id>/resolved/` — engineer/admin only
(`PermissionDenied` → 403 for staff). Same 30-day window as the dashboard.

`resolved_complaints_for_engineer(user, window_start, window_end) -> list[dict]`
returns, for each complaint the engineer is credited with:
`{complaint_id, equipment (name/model_number/serial_number/pk), resolution_type
(Repaired / Duplicate / No fault), resolved_at, remarks}` where `remarks` is:
- for a repair (`close_reason=resolved`): the work order's `Remark` texts
  (notes, delay, and completion remark), most-recent-relevant first;
- for duplicate / no-fault: the complaint's `close_note`.

Template lists them in a table: equipment (linked to equipment detail),
resolution type, date, remarks. Header shows the engineer's name and total.

## 5. Feature 2 — Staff confirmation loop

### 5.1 Becoming "awaiting confirmation"
No new write is needed at completion time — the derived rule in §3 makes a
complaint "awaiting confirmation" the moment `complete_work_order` closes it as
`resolved` with `outcome=repaired`.

### 5.2 Staff side (the reporter answers)
- On **My Complaints**, complaints awaiting confirmation render a highlighted
  row: **"Is the machine functional now?"** with two buttons — **Yes,
  functional** / **No, not functional**.
- A small header banner shows the pending count ("You have N complaints to
  confirm"). Non-blocking — the rest of the app stays usable; the prompt
  persists across sessions until answered.
- Service `confirm_complaint(complaint, actor, is_functional) -> Complaint`:
  - only the complaint's **reporter** may confirm (else `PermissionDenied`);
  - only valid while awaiting confirmation (else `WorkOrderStateError`);
  - sets `functional_confirmation` + `confirmed_at`; writes AuditLog
    `"complaint.confirmed"`. Atomic.
- View `POST /maintenance/complaints/<pk>/confirm/` (login required; the
  reporter check lives in the service).

### 5.3 Engineer side (sees the answer — derived, no inbox)
- **Work-order detail**: each attached complaint shows its confirmation state —
  *Awaiting staff confirmation* / *Staff confirmed: Functional ✓* / *Staff
  reported: NOT functional ✗*.
- **Dashboard panel "Recent staff confirmations" (last 30 days)**: lists
  complaints with a confirmation set in the window, each linked to its work
  order, with **not-functional entries highlighted**. Engineer/admin only.
  `recent_confirmations(window_start, window_end) -> list[dict]` derived from
  `Complaint` (`confirmed_at` in window), newest first.

### 5.4 "Not functional" behavior
Purely informational: it appears (highlighted) in the engineer's views. No
status change, no auto-reopen. The engineer opens a new work order manually if
warranted (normal flow; equipment is `working`).

## 6. Visibility tightening (work orders)

- `workorder_detail` view gains an engineer/admin gate (`_require_engineer`),
  returning 403 for staff.
- `templates/equipment/detail.html`: for staff, render work-order references as
  plain text (`WO #N`) instead of links; keep links for engineers/admins.
- No other view changes; `my_complaints` already scopes to the reporter.

## 7. Out of scope (explicitly)

No auto-reopen on "not functional"; no email/SMTP; no read/unread notification
state or bell/inbox; no scheduled auto-close of unanswered prompts; no change to
the status machine, the one-active-work-order rule, condemnation, or append-only
guarantees. Confirmation is not requested for duplicates, false-alarms, or
condemned outcomes.

## 8. Testing

Service/metric layer first (pytest, real Postgres):
1. `resolving_engineer_ids` — participants for a repair (multi-engineer),
   `closed_by` for duplicate/no-fault.
2. `per_engineer_resolved` — shared repair credits every participant; window
   filtering by `closed_at`; zero-count engineers excluded.
3. `resolved_complaints_for_engineer` — correct equipment + remarks per
   resolution type.
4. `confirm_complaint` — only the reporter may confirm (staff-not-reporter and
   engineer both denied); sets fields; blocks a second confirmation; audited.
5. Awaiting-confirmation derivation — true only for resolved+repaired+null;
   false for duplicate/no-fault/condemned/already-confirmed.
6. `recent_confirmations` — window filter, not-functional included.

View/access layer:
7. Drill-down 403 for staff, 200 for engineer, lists the right rows.
8. `workorder_detail` now 403 for staff, 200 for engineer/admin.
9. Staff can confirm their own complaint via the view; another staff/engineer
   cannot; My Complaints shows the prompt only while pending.
10. Dashboard shows the single "Complaints resolved" column and the
    confirmations panel for engineers.

## 9. File touch-list (informing the plan)

- `apps/maintenance/models.py` — `FunctionalConfirmation` choices + two fields;
  new migration.
- `apps/maintenance/services.py` — `confirm_complaint`.
- `apps/maintenance/views.py` — `confirm` view; `_require_engineer` on
  `workorder_detail`.
- `apps/maintenance/urls.py` — confirm route.
- `apps/reports/metrics.py` — `resolving_engineer_ids`,
  `per_engineer_resolved`, `resolved_complaints_for_engineer`,
  `recent_confirmations`; remove/replace `per_engineer_activity`.
- `apps/reports/views.py` + `urls.py` — drill-down view/route; dashboard context
  (resolved counts + confirmations panel).
- Templates — `reports/dashboard.html` (single column + panel),
  new `reports/engineer_resolved.html`, `maintenance/my_complaints.html`
  (confirm prompt + banner), `maintenance/workorder_detail.html` (confirmation
  state), `equipment/detail.html` (plain-text WO refs for staff).
- Tests — `tests/test_metrics.py` (update), `tests/test_confirmation.py` (new),
  `tests/test_maintenance_views.py` / `tests/test_dashboard_view.py` (updates).

All timestamps UTC; display in the configured timezone. Numbers come from
SQL/ORM; no LLM anywhere in this feature.
