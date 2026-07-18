# Complaints-Resolved Metric + Staff Confirmation Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single clickable "Complaints resolved" per-engineer dashboard metric (with a drill-down), a staff "is the machine functional now?" confirmation loop after repairs, and tighten work-order detail visibility to engineers/admins.

**Architecture:** Server-rendered Django, all state changes through `services.py`. Two new `Complaint` fields; "awaiting confirmation" and all notifications are **derived from state** (no new tables, no email). Metric attribution: repair-resolved complaints credit every work-order participant, duplicate/no-fault credit the closer. Spec: `docs/superpowers/specs/2026-07-18-complaints-resolved-and-confirmation-design.md`.

**Tech Stack:** Python 3.12, Django ~5.2, PostgreSQL, pytest-django, HTMX/Alpine/Tailwind (vendored), uv. Run tests with `uv run pytest`; run one file with `uv run pytest tests/<file>.py -v`. Postgres must be up: `docker compose up -d db`.

## Global Constraints

- **Single-line commit messages** (user preference): `git commit -m "type: summary"` — no body.
- All state changes go through `services.py`; role checks re-checked in services (raise `django.core.exceptions.PermissionDenied`).
- Append-only/no-delete unchanged: `Complaint` stays `NoDeleteModel`; never hard-delete; every mutation writes an `AuditLog` via `apps.core.audit.record`.
- **Attribution:** repair-resolved complaint → credit every `work_order.participants`; duplicate/no-fault → credit `complaint.closed_by`.
- **Awaiting confirmation is DERIVED, never stored:** `status=closed` AND `close_reason=resolved` AND `work_order.outcome=repaired` AND `functional_confirmation IS NULL`. Never asked for duplicate/no-fault/condemned.
- **"Not functional" is informational only** — no auto-reopen, no status change.
- **Notifications derived from state** — no notification table, no email/SMTP, no read/unread.
- Only a complaint's **reporter** may confirm it.
- Dashboard/metric window: rolling 30 days by `closed_at` (metric) / `confirmed_at` (confirmations panel).
- Timestamps UTC via `django.utils.timezone.now()`; numbers from ORM, no LLM.
- Enum values exact: `FunctionalConfirmation.FUNCTIONAL="functional"`, `NOT_FUNCTIONAL="not_functional"`.
- Existing names to reuse: `apps.equipment.services._require_engineer_or_admin`, `apps.maintenance.views._require_engineer`, `apps.core.audit.record`, `apps.core.exceptions.WorkOrderStateError`, `CloseReason`, `ComplaintStatus`, `WorkOrderOutcome`, `WorkOrderStatus`.

---

### Task 1: Complaint confirmation fields + migration

**Files:**
- Modify: `apps/maintenance/models.py`
- Test: `tests/test_confirmation.py` (create)

**Interfaces:**
- Produces: `maintenance.models.FunctionalConfirmation` (TextChoices: `FUNCTIONAL="functional"`, `NOT_FUNCTIONAL="not_functional"`); `Complaint.functional_confirmation` (nullable char), `Complaint.confirmed_at` (nullable datetime).

- [ ] **Step 1: Write the failing test**

`tests/test_confirmation.py`:
```python
import pytest

from apps.maintenance.models import Complaint, FunctionalConfirmation

pytestmark = pytest.mark.django_db


def test_complaint_confirmation_fields_default_null(equipment, staff_user):
    c = Complaint.objects.create(
        equipment=equipment, reporter=staff_user, description="x"
    )
    assert c.functional_confirmation is None
    assert c.confirmed_at is None


def test_functional_confirmation_choices():
    assert FunctionalConfirmation.FUNCTIONAL == "functional"
    assert FunctionalConfirmation.NOT_FUNCTIONAL == "not_functional"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_confirmation.py -v`
Expected: FAIL — `ImportError` on `FunctionalConfirmation`.

- [ ] **Step 3: Implement**

In `apps/maintenance/models.py`, add the choices class near the other TextChoices (after `RemarkKind`):
```python
class FunctionalConfirmation(models.TextChoices):
    FUNCTIONAL = "functional", "Functional"
    NOT_FUNCTIONAL = "not_functional", "Not functional"
```

Add two fields to `class Complaint` (after `closed_at`):
```python
    functional_confirmation = models.CharField(
        max_length=20, choices=FunctionalConfirmation.choices, null=True, blank=True
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 4: Migrate and run tests**

Run:
```
uv run python manage.py makemigrations maintenance
uv run pytest tests/test_confirmation.py -v
```
Expected: migration created; both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/maintenance/models.py apps/maintenance/migrations tests/test_confirmation.py
git commit -m "feat: add functional_confirmation fields to Complaint"
```

---

### Task 2: `is_awaiting_confirmation` derivation helper

**Files:**
- Modify: `apps/maintenance/models.py`
- Test: `tests/test_confirmation.py`

**Interfaces:**
- Consumes: Task 1 fields; `CloseReason`, `ComplaintStatus`, `WorkOrderOutcome`.
- Produces: `Complaint.is_awaiting_confirmation` (property → bool).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_confirmation.py`:
```python
from apps.maintenance.models import CloseReason, ComplaintStatus, WorkOrderOutcome, WorkOrderStatus
from apps.maintenance.services import (
    complete_work_order, lodge_complaint, open_work_order, start_repair,
)
from apps.equipment.services import condemn_equipment
from apps.maintenance.models import FaultCategory


def test_awaiting_confirmation_true_after_repair(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    complaint.refresh_from_db()
    assert complaint.status == ComplaintStatus.CLOSED
    assert complaint.close_reason == CloseReason.RESOLVED
    assert complaint.is_awaiting_confirmation is True


def test_not_awaiting_for_open_complaint(equipment, staff_user):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    assert complaint.is_awaiting_confirmation is False


def test_not_awaiting_after_condemnation(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    condemn_equipment(equipment, engineer, remark="dead", condemned_location="store")
    complaint.refresh_from_db()
    assert complaint.status == ComplaintStatus.CLOSED
    assert complaint.is_awaiting_confirmation is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_confirmation.py -v`
Expected: FAIL — `Complaint` has no `is_awaiting_confirmation`.

- [ ] **Step 3: Implement**

Add to `class Complaint` (a property, after the fields):
```python
    @property
    def is_awaiting_confirmation(self) -> bool:
        return (
            self.status == ComplaintStatus.CLOSED
            and self.close_reason == CloseReason.RESOLVED
            and self.functional_confirmation is None
            and self.work_order_id is not None
            and self.work_order.outcome == WorkOrderOutcome.REPAIRED
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_confirmation.py -v`
Expected: all PASS. (Condemnation closes the complaint as resolved but the work order outcome is `condemned`, so `is_awaiting_confirmation` is False.)

- [ ] **Step 5: Commit**

```bash
git add apps/maintenance/models.py tests/test_confirmation.py
git commit -m "feat: add is_awaiting_confirmation derivation to Complaint"
```

---

### Task 3: `confirm_complaint` service

**Files:**
- Modify: `apps/maintenance/services.py`
- Test: `tests/test_confirmation.py`

**Interfaces:**
- Consumes: Task 1/2; `apps.core.audit.record`, `apps.core.exceptions.WorkOrderStateError`, `FunctionalConfirmation`.
- Produces: `apps.maintenance.services.confirm_complaint(complaint, actor, is_functional: bool) -> Complaint`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_confirmation.py`:
```python
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import WorkOrderStateError
from apps.core.models import AuditLog
from apps.maintenance.services import confirm_complaint


def _resolved_complaint(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    complaint.refresh_from_db()
    return complaint


def test_reporter_confirms_functional(equipment, staff_user, engineer):
    complaint = _resolved_complaint(equipment, staff_user, engineer)
    confirm_complaint(complaint, staff_user, is_functional=True)
    complaint.refresh_from_db()
    assert complaint.functional_confirmation == FunctionalConfirmation.FUNCTIONAL
    assert complaint.confirmed_at is not None
    assert complaint.is_awaiting_confirmation is False
    assert AuditLog.objects.filter(verb="complaint.confirmed").count() == 1


def test_reporter_confirms_not_functional(equipment, staff_user, engineer):
    complaint = _resolved_complaint(equipment, staff_user, engineer)
    confirm_complaint(complaint, staff_user, is_functional=False)
    complaint.refresh_from_db()
    assert complaint.functional_confirmation == FunctionalConfirmation.NOT_FUNCTIONAL


def test_non_reporter_cannot_confirm(equipment, staff_user, engineer, admin_user):
    complaint = _resolved_complaint(equipment, staff_user, engineer)
    with pytest.raises(PermissionDenied):
        confirm_complaint(complaint, admin_user, is_functional=True)


def test_cannot_confirm_twice(equipment, staff_user, engineer):
    complaint = _resolved_complaint(equipment, staff_user, engineer)
    confirm_complaint(complaint, staff_user, is_functional=True)
    with pytest.raises(WorkOrderStateError):
        confirm_complaint(complaint, staff_user, is_functional=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_confirmation.py -v`
Expected: FAIL — `confirm_complaint` does not exist.

- [ ] **Step 3: Implement**

Add `FunctionalConfirmation` to the model imports at the top of `apps/maintenance/services.py` (extend the existing `from .models import (...)` block), then append:
```python
@transaction.atomic
def confirm_complaint(complaint, actor, is_functional) -> Complaint:
    if complaint.reporter_id != actor.id:
        raise PermissionDenied("Only the reporter can confirm this complaint.")
    if not complaint.is_awaiting_confirmation:
        raise WorkOrderStateError("This complaint is not awaiting confirmation.")
    complaint.functional_confirmation = (
        FunctionalConfirmation.FUNCTIONAL
        if is_functional
        else FunctionalConfirmation.NOT_FUNCTIONAL
    )
    complaint.confirmed_at = timezone.now()
    complaint.save(update_fields=["functional_confirmation", "confirmed_at"])
    audit.record(actor, "complaint.confirmed", complaint,
                 {"functional": is_functional})
    return complaint
```
(`transaction`, `timezone`, `audit`, `PermissionDenied`, `WorkOrderStateError` are already imported in this file.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_confirmation.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/maintenance/services.py tests/test_confirmation.py
git commit -m "feat: add confirm_complaint service (reporter-only, audited)"
```

---

### Task 4: Metric functions (attribution, per-engineer counts, drill-down, confirmations)

**Files:**
- Modify: `apps/reports/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `Complaint`, `CloseReason`, `ComplaintStatus`, `FunctionalConfirmation`, `User`.
- Produces (in `apps.reports.metrics`):
  - `resolving_engineer_ids(complaint) -> set[int]`
  - `per_engineer_resolved(window_start, window_end) -> list[dict]` (`{user_id, name, employee_id, resolved_count}`, count>0, desc)
  - `resolved_complaints_for_engineer(user, window_start, window_end) -> list[dict]` (`{complaint_id, equipment_name, equipment_model, equipment_serial, equipment_id, resolution_type, resolved_at, remarks}`)
  - `recent_confirmations(window_start, window_end) -> list[dict]` (`{complaint_id, equipment, work_order_id, is_functional, confirmed_at}`, newest first)
  - Remove `per_engineer_activity` (replaced).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metrics.py` (imports already include timedelta/timezone/services there):
```python
def test_resolved_credits_all_participants(equipment, staff_user, engineer, engineer2):
    from apps.maintenance.services import (
        complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory
    now = timezone.now()
    lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer2, fault_category=FaultCategory.MECHANICAL,
                        participants=[engineer])
    rows = {r["employee_id"]: r for r in
            metrics.per_engineer_resolved(now - timedelta(days=1), timezone.now())}
    assert rows["EMP-100"]["resolved_count"] == 1  # participant
    assert rows["EMP-101"]["resolved_count"] == 1  # completer, auto-participant


def test_resolved_credits_closer_for_duplicate(equipment, staff_user, engineer):
    from apps.maintenance.services import close_complaint, lodge_complaint
    from apps.maintenance.models import CloseReason
    now = timezone.now()
    first = lodge_complaint(staff_user, equipment, "broken")
    dup = lodge_complaint(staff_user, equipment, "also broken")
    close_complaint(dup, engineer, CloseReason.DUPLICATE, duplicate_of=first,
                    close_note="dup")
    rows = {r["employee_id"]: r for r in
            metrics.per_engineer_resolved(now - timedelta(days=1), timezone.now())}
    assert rows["EMP-100"]["resolved_count"] == 1


def test_drilldown_lists_equipment_and_remarks(equipment, staff_user, engineer):
    from apps.maintenance.services import (
        add_remark, complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory
    now = timezone.now()
    lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    add_remark(wo, engineer, "ordered parts, installed, verified")
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    rows = metrics.resolved_complaints_for_engineer(
        engineer, now - timedelta(days=1), timezone.now())
    assert len(rows) == 1
    assert rows[0]["equipment_serial"] == "SN-0001"
    assert rows[0]["resolution_type"] == "Repaired"
    assert any("ordered parts" in r for r in rows[0]["remarks"])


def test_recent_confirmations_lists_not_functional(equipment, staff_user, engineer):
    from apps.maintenance.services import (
        complete_work_order, confirm_complaint, lodge_complaint, open_work_order,
        start_repair,
    )
    from apps.maintenance.models import FaultCategory
    now = timezone.now()
    complaint = lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    complaint.refresh_from_db()
    confirm_complaint(complaint, staff_user, is_functional=False)
    rows = metrics.recent_confirmations(now - timedelta(days=1), timezone.now())
    assert len(rows) == 1
    assert rows[0]["is_functional"] is False
    assert rows[0]["work_order_id"] == wo.pk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_metrics.py -k "resolved or confirmations or drilldown" -v`
Expected: FAIL — new metric functions do not exist.

- [ ] **Step 3: Implement**

In `apps/reports/metrics.py`: extend imports to include `ComplaintStatus`, `FunctionalConfirmation` from `apps.maintenance.models` (they already import `CloseReason, Complaint, ...`). Delete the `per_engineer_activity` function and add:
```python
def resolving_engineer_ids(complaint):
    if complaint.work_order_id is not None:
        ids = {u.id for u in complaint.work_order.participants.all()}
        if ids:
            return ids
    return {complaint.closed_by_id} if complaint.closed_by_id else set()


RESOLVED_REASONS = [CloseReason.RESOLVED, CloseReason.DUPLICATE, CloseReason.NO_FAULT]


def _resolved_complaints(window_start, window_end):
    return (
        Complaint.objects.filter(
            status=ComplaintStatus.CLOSED,
            close_reason__in=RESOLVED_REASONS,
            closed_at__range=(window_start, window_end),
        )
        .select_related("equipment", "work_order")
        .prefetch_related("work_order__participants")
    )


def per_engineer_resolved(window_start, window_end):
    from apps.accounts.models import User

    counts = {}
    for complaint in _resolved_complaints(window_start, window_end):
        for uid in resolving_engineer_ids(complaint):
            counts[uid] = counts.get(uid, 0) + 1
    users = {u.id: u for u in User.objects.filter(id__in=counts)}
    rows = [
        {
            "user_id": uid,
            "name": users[uid].get_full_name() or users[uid].username,
            "employee_id": users[uid].employee_id,
            "resolved_count": n,
        }
        for uid, n in counts.items()
        if uid in users
    ]
    return sorted(rows, key=lambda r: -r["resolved_count"])


_RESOLUTION_LABEL = {
    CloseReason.RESOLVED: "Repaired",
    CloseReason.DUPLICATE: "Duplicate",
    CloseReason.NO_FAULT: "No fault",
}


def resolved_complaints_for_engineer(user, window_start, window_end):
    rows = []
    for complaint in _resolved_complaints(window_start, window_end):
        if user.id not in resolving_engineer_ids(complaint):
            continue
        if complaint.close_reason == CloseReason.RESOLVED and complaint.work_order_id:
            remarks = [r.text for r in complaint.work_order.remarks.all()]
        else:
            remarks = [complaint.close_note] if complaint.close_note else []
        eq = complaint.equipment
        rows.append({
            "complaint_id": complaint.id,
            "equipment_id": eq.id,
            "equipment_name": eq.name,
            "equipment_model": eq.model_number,
            "equipment_serial": eq.serial_number,
            "resolution_type": _RESOLUTION_LABEL[complaint.close_reason],
            "resolved_at": complaint.closed_at,
            "remarks": remarks,
        })
    return sorted(rows, key=lambda r: r["resolved_at"], reverse=True)


def recent_confirmations(window_start, window_end):
    rows = (
        Complaint.objects.filter(
            functional_confirmation__isnull=False,
            confirmed_at__range=(window_start, window_end),
        )
        .select_related("equipment")
        .order_by("-confirmed_at")
    )
    return [
        {
            "complaint_id": c.id,
            "equipment": str(c.equipment),
            "work_order_id": c.work_order_id,
            "is_functional": c.functional_confirmation
            == FunctionalConfirmation.FUNCTIONAL,
            "confirmed_at": c.confirmed_at,
        }
        for c in rows
    ]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: new tests PASS. The Phase-1 test `test_per_engineer_activity_counts_participation` in `tests/test_metrics.py` references the removed `per_engineer_activity` function — **delete that one test** (it is replaced by `test_resolved_credits_all_participants`) and note the deletion in the report. Then run the whole file: `uv run pytest tests/test_metrics.py -v`.

- [ ] **Step 5: Commit**

```bash
git add apps/reports/metrics.py tests/test_metrics.py
git commit -m "feat: complaints-resolved metric functions with participant attribution"
```

---

### Task 5: Dashboard wiring + engineer drill-down view

**Files:**
- Modify: `apps/reports/views.py`, `apps/reports/urls.py`, `templates/reports/dashboard.html`
- Create: `templates/reports/engineer_resolved.html`
- Test: `tests/test_dashboard_view.py`

**Interfaces:**
- Consumes: Task 4 metrics; `_require_engineer_or_admin` pattern (dashboard already checks `is_engineer_or_admin`).
- Produces: URL name `engineer_resolved` (`/dashboard/engineer/<int:user_id>/resolved/`); dashboard context keys `resolved` (list) and `confirmations` (list).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dashboard_view.py`:
```python
def test_dashboard_shows_complaints_resolved(client, engineer, staff_user, equipment):
    from apps.maintenance.services import (
        complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory
    lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    client.force_login(engineer)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"Complaints resolved" in response.content


def test_drilldown_requires_engineer(client, staff_user, engineer):
    client.force_login(staff_user)
    assert client.get(
        reverse("engineer_resolved", args=[engineer.pk])).status_code == 403


def test_drilldown_lists_resolved(client, engineer, staff_user, equipment):
    from apps.maintenance.services import (
        complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory
    lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    client.force_login(engineer)
    response = client.get(reverse("engineer_resolved", args=[engineer.pk]))
    assert response.status_code == 200
    assert b"SN-0001" in response.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard_view.py -v`
Expected: FAIL — `NoReverseMatch` for `engineer_resolved`; dashboard lacks the string.

- [ ] **Step 3: Implement**

In `apps/reports/views.py`, replace the `engineers` context key computation and add the drill-down view. Update `dashboard`'s context: replace the old `"engineers": metrics.per_engineer_activity(...)` line with:
```python
        "resolved": metrics.per_engineer_resolved(window_start, window_end),
        "confirmations": metrics.recent_confirmations(window_start, window_end),
```
Append the new view:
```python
@login_required
def engineer_resolved(request, user_id):
    if not request.user.is_engineer_or_admin:
        raise PermissionDenied
    from django.contrib.auth import get_user_model

    window_end = timezone.now()
    window_start = window_end - timedelta(days=30)
    engineer = get_object_or_404(get_user_model(), pk=user_id)
    rows = metrics.resolved_complaints_for_engineer(
        engineer, window_start, window_end)
    return render(request, "reports/engineer_resolved.html", {
        "engineer": engineer, "rows": rows, "total": len(rows),
    })
```
Add imports at the top of `views.py` if missing: `from django.shortcuts import get_object_or_404, render`.

`apps/reports/urls.py` — add:
```python
    path("engineer/<int:user_id>/resolved/", views.engineer_resolved,
         name="engineer_resolved"),
```

In `templates/reports/dashboard.html`, replace the entire "Engineer activity" `<div class="rounded bg-white p-4 shadow">…</div>` block (the one containing the engineers table) with:
```html
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-1 font-semibold">Complaints resolved <span class="font-normal
      text-slate-500">· last 30 days · per engineer</span></h2>
    <p class="mb-3 text-xs text-slate-500">
      Complaints an engineer helped resolve — by completing the repair (credits
      everyone who worked on it) or by closing a duplicate / false alarm. Click a
      number to see which equipment and the remarks.
    </p>
    <table class="w-full text-sm">
      <thead><tr class="border-b text-left">
        <th class="py-1">Engineer</th>
        <th class="py-1">Complaints resolved</th></tr></thead>
      <tbody>
        {% for e in resolved %}
        <tr class="border-b"><td class="py-1">{{ e.name }}
          <span class="text-slate-500">({{ e.employee_id }})</span></td>
          <td class="py-1"><a class="text-sky-700 hover:underline"
            href="{% url 'engineer_resolved' e.user_id %}">{{ e.resolved_count }}</a></td></tr>
        {% empty %}<tr><td colspan="2" class="py-2 text-slate-500">
          No complaints resolved in this window.</td></tr>{% endfor %}
      </tbody>
    </table>
  </div>
  <div class="rounded bg-white p-4 shadow">
    <h2 class="mb-2 font-semibold">Recent staff confirmations <span
      class="font-normal text-slate-500">· last 30 days</span></h2>
    <ul class="space-y-2 text-sm">
      {% for c in confirmations %}
      <li class="rounded p-2 {% if c.is_functional %}bg-emerald-50
          {% else %}bg-red-50 border border-red-200{% endif %}">
        {% if c.work_order_id %}<a class="text-sky-700 hover:underline"
          href="{% url 'workorder_detail' c.work_order_id %}">WO #{{ c.work_order_id }}</a>
        {% endif %} — {{ c.equipment }}:
        {% if c.is_functional %}<span class="text-emerald-800">Functional ✓</span>
        {% else %}<span class="font-medium text-red-800">NOT functional ✗</span>{% endif %}
        <span class="text-slate-500">· {{ c.confirmed_at|timesince }} ago</span>
      </li>
      {% empty %}<li class="text-slate-500">No confirmations yet.</li>{% endfor %}
    </ul>
  </div>
```

`templates/reports/engineer_resolved.html`:
```html
{% extends "base.html" %}
{% block title %}Complaints resolved — {{ engineer }}{% endblock %}
{% block content %}
<div class="mb-4">
  <a href="{% url 'dashboard' %}" class="text-sm text-sky-700 hover:underline">← Dashboard</a>
  <h1 class="text-2xl font-bold">Complaints resolved by {{ engineer.get_full_name|default:engineer.username }}
    <span class="text-base font-normal text-slate-500">({{ engineer.employee_id }}) · {{ total }} · last 30 days</span></h1>
</div>
<table class="w-full rounded bg-white shadow text-sm">
  <thead><tr class="border-b text-left">
    <th class="p-3">Equipment</th><th class="p-3">Type</th>
    <th class="p-3">Resolved</th><th class="p-3">Remarks</th></tr></thead>
  <tbody>
    {% for r in rows %}
    <tr class="border-b align-top">
      <td class="p-3"><a class="text-sky-700 hover:underline"
        href="{% url 'equipment_detail' r.equipment_id %}">{{ r.equipment_name }}</a>
        <div class="text-slate-500">{{ r.equipment_model }} ·
          <span class="font-mono">{{ r.equipment_serial }}</span></div></td>
      <td class="p-3">{{ r.resolution_type }}</td>
      <td class="p-3">{{ r.resolved_at|date:"Y-m-d H:i" }}</td>
      <td class="p-3">
        {% for remark in r.remarks %}<div>“{{ remark }}”</div>{% empty %}
        <span class="text-slate-500">—</span>{% endfor %}</td>
    </tr>
    {% empty %}
    <tr><td colspan="4" class="p-6 text-center text-slate-500">
      Nothing resolved in this window.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 4: Rebuild CSS and run tests**

Run:
```
bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify
uv run pytest tests/test_dashboard_view.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/reports static/css/app.css templates/reports tests/test_dashboard_view.py
git commit -m "feat: dashboard complaints-resolved column, drill-down, confirmations panel"
```

---

### Task 6: Staff confirmation UI (My Complaints prompt) + confirm view

**Files:**
- Modify: `apps/maintenance/views.py`, `apps/maintenance/urls.py`, `templates/maintenance/my_complaints.html`
- Test: `tests/test_maintenance_views.py`

**Interfaces:**
- Consumes: `confirm_complaint` (Task 3).
- Produces: URL name `complaint_confirm` (`POST /maintenance/complaints/<int:pk>/confirm/`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_maintenance_views.py`:
```python
def test_staff_confirms_via_view(client, staff_user, engineer, equipment):
    from apps.maintenance.services import (
        complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory, FunctionalConfirmation
    complaint = lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    client.force_login(staff_user)
    response = client.post(reverse("complaint_confirm", args=[complaint.pk]),
                           {"functional": "yes"})
    assert response.status_code == 302
    complaint.refresh_from_db()
    assert complaint.functional_confirmation == FunctionalConfirmation.FUNCTIONAL


def test_my_complaints_shows_confirm_prompt(client, staff_user, engineer, equipment):
    from apps.maintenance.services import (
        complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory
    lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    client.force_login(staff_user)
    response = client.get(reverse("my_complaints"))
    assert b"functional now" in response.content


def test_other_staff_cannot_confirm(client, staff_user, engineer, equipment):
    from apps.maintenance.services import (
        complete_work_order, lodge_complaint, open_work_order, start_repair,
    )
    from apps.maintenance.models import FaultCategory
    from django.contrib.auth import get_user_model
    complaint = lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    other = get_user_model().objects.create_user(
        username="nurse2", password="pw", employee_id="EMP-002", role="staff")
    client.force_login(other)
    assert client.post(reverse("complaint_confirm", args=[complaint.pk]),
                       {"functional": "yes"}).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_maintenance_views.py -k confirm -v`
Expected: FAIL — `NoReverseMatch` for `complaint_confirm`.

- [ ] **Step 3: Implement**

In `apps/maintenance/views.py`, add (uses existing `require_POST`, `login_required`, `messages`, `get_object_or_404`, `Complaint`, `DomainError`):
```python
@login_required
@require_POST
def complaint_confirm(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)
    is_functional = request.POST.get("functional") == "yes"
    try:
        services.confirm_complaint(complaint, request.user, is_functional)
    except (DomainError, PermissionDenied) as exc:
        if isinstance(exc, PermissionDenied):
            raise
        messages.error(request, str(exc))
    else:
        messages.success(request, "Thank you — your response was recorded.")
    return redirect("my_complaints")
```
Ensure `from django.core.exceptions import PermissionDenied` is imported in the file (it is used by `_require_engineer`). Add if absent.

`apps/maintenance/urls.py` — add:
```python
    path("complaints/<int:pk>/confirm/", views.complaint_confirm,
         name="complaint_confirm"),
```

In `templates/maintenance/my_complaints.html`, inside the row loop, add a confirm prompt. After the status cell, add a full-width prompt row when awaiting. Replace the table body row block so each complaint is followed by a conditional prompt:
```html
    {% for c in complaints %}
    <tr class="border-b">
      <td class="p-3">{{ c.pk }}</td>
      <td class="p-3">{{ c.equipment.name }}
        <span class="font-mono text-slate-500">{{ c.equipment.serial_number }}</span></td>
      <td class="p-3">{{ c.description|truncatechars:80 }}</td>
      <td class="p-3">{{ c.created_at }}</td>
      <td class="p-3">{{ c.get_status_display }}
        {% if c.close_reason %}<span class="text-slate-500">
          ({{ c.get_close_reason_display }})</span>{% endif %}</td>
    </tr>
    {% if c.is_awaiting_confirmation %}
    <tr class="border-b bg-amber-50">
      <td colspan="5" class="p-3">
        <form method="post" action="{% url 'complaint_confirm' c.pk %}"
              class="flex items-center gap-3">
          {% csrf_token %}
          <span class="font-medium">Is the machine functional now?</span>
          <button name="functional" value="yes"
            class="rounded bg-emerald-700 px-3 py-1 text-white">Yes, functional</button>
          <button name="functional" value="no"
            class="rounded bg-red-700 px-3 py-1 text-white">No, not functional</button>
        </form>
      </td>
    </tr>
    {% endif %}
    {% empty %}
    <tr><td colspan="5" class="p-6 text-center text-slate-500">
      You have not lodged any complaints.</td></tr>
    {% endfor %}
```
Compute the pending count in the view and add a banner. Update the `my_complaints` view:
```python
@login_required
def my_complaints(request):
    complaints = (Complaint.objects.filter(reporter=request.user)
                  .select_related("equipment", "work_order"))
    pending = sum(1 for c in complaints if c.is_awaiting_confirmation)
    return render(request, "maintenance/my_complaints.html",
                  {"complaints": complaints, "pending_confirmations": pending})
```
And the banner under the `<h1>` in `my_complaints.html`:
```html
{% if pending_confirmations %}
<div class="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-2 text-amber-800">
  You have {{ pending_confirmations }} repaired complaint{{ pending_confirmations|pluralize }}
  to confirm below.
</div>
{% endif %}
```

- [ ] **Step 4: Rebuild CSS and run tests**

Run:
```
bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify
uv run pytest tests/test_maintenance_views.py -k "confirm or my_complaints" -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/maintenance static/css/app.css templates/maintenance/my_complaints.html tests/test_maintenance_views.py
git commit -m "feat: staff confirmation prompt and confirm view on My Complaints"
```

---

### Task 7: Work-order detail confirmation status + tighten visibility

**Files:**
- Modify: `apps/maintenance/views.py`, `templates/maintenance/workorder_detail.html`, `templates/equipment/detail.html`
- Test: `tests/test_maintenance_views.py`

**Interfaces:**
- Consumes: `_require_engineer`, `Complaint.functional_confirmation`.
- Produces: `workorder_detail` now engineer/admin-only; WO detail shows per-complaint confirmation status; staff see plain-text WO refs on equipment detail.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_maintenance_views.py`:
```python
def test_workorder_detail_forbidden_for_staff(client, staff_user, engineer, equipment):
    from apps.maintenance.services import open_work_order
    wo = open_work_order(equipment, engineer)
    client.force_login(staff_user)
    assert client.get(reverse("workorder_detail", args=[wo.pk])).status_code == 403


def test_workorder_detail_shows_confirmation(client, engineer, staff_user, equipment):
    from apps.maintenance.services import (
        complete_work_order, confirm_complaint, lodge_complaint, open_work_order,
        start_repair,
    )
    from apps.maintenance.models import FaultCategory
    complaint = lodge_complaint(staff_user, equipment, "no power")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, fault_category=FaultCategory.ELECTRICAL)
    complaint.refresh_from_db()
    confirm_complaint(complaint, staff_user, is_functional=False)
    client.force_login(engineer)
    response = client.get(reverse("workorder_detail", args=[wo.pk]))
    assert b"NOT functional" in response.content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_maintenance_views.py -k "workorder_detail" -v`
Expected: FAIL — staff currently gets 200 (no gate); confirmation string absent.

- [ ] **Step 3: Implement**

In `apps/maintenance/views.py`, add the guard to `workorder_detail` (first line of the function body, before the query):
```python
    _require_engineer(request.user)
```

In `templates/maintenance/workorder_detail.html`, inside the "Attached Complaints" loop, append the confirmation state to each complaint `<li>` (after the reporter/status line):
```html
        {% if c.is_awaiting_confirmation %}
        <div class="text-amber-700">Awaiting staff confirmation</div>
        {% elif c.functional_confirmation == 'functional' %}
        <div class="text-emerald-700">Staff confirmed: Functional ✓</div>
        {% elif c.functional_confirmation == 'not_functional' %}
        <div class="font-medium text-red-700">Staff reported: NOT functional ✗</div>
        {% endif %}
```

In `templates/equipment/detail.html`, the Work Orders list currently links each WO. Make the link engineer/admin-only, plain text for staff. Replace the WO anchor line:
```html
    {% if can_engineer %}
    <a class="font-medium text-sky-700 hover:underline"
       href="{% url 'workorder_detail' wo.pk %}">WO #{{ wo.pk }}</a>
    {% else %}
    <span class="font-medium">WO #{{ wo.pk }}</span>
    {% endif %}
```
(`can_engineer` is already in the equipment detail context.)

- [ ] **Step 4: Rebuild CSS and run tests**

Run:
```
bin/tailwindcss.exe -i static/css/input.css -o static/css/app.css --minify
uv run pytest tests/test_maintenance_views.py -k "workorder_detail" -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/maintenance/views.py templates/maintenance/workorder_detail.html templates/equipment/detail.html static/css/app.css tests/test_maintenance_views.py
git commit -m "feat: WO detail confirmation status; restrict WO detail to engineers"
```

---

### Task 8: Full-suite verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -q`
Expected: all pass (Phase 1's 81 + the new tests; any deleted `per_engineer_activity` tests removed in Task 4).

- [ ] **Step 2: Lint**

Run: `uv run ruff check` then `uv run ruff format --check`
Expected: clean. If `ruff format --check` reports files, run `uv run ruff format` and re-run the suite.

- [ ] **Step 3: Commit any formatting**

```bash
git add -u
git commit -m "style: ruff format for confirmation feature"
```
(Skip if nothing changed. Do NOT `git add` untracked files like `practic.ipynb`.)

---

## Out of scope (per spec)

No auto-reopen on "not functional"; no email/SMTP; no read/unread state; no scheduled auto-close; no status-machine or condemnation changes. Confirmation is never requested for duplicate/no-fault/condemned outcomes.
