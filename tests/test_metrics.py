from datetime import timedelta

import pytest
from django.utils import timezone

from apps.maintenance.models import (
    CloseReason, Complaint, FaultCategory, WorkOrder, WorkOrderStatus,
)
from apps.maintenance.services import (
    close_complaint, complete_work_order, lodge_complaint, open_work_order,
    add_remark, start_repair,
)
from apps.reports import metrics

pytestmark = pytest.mark.django_db

NOW = None  # set per-test via timezone.now()


def _backdate(obj, **fields):
    """Seed/test helper: bypass auto_now_add/append-only via queryset update."""
    type(obj).objects.filter(pk=obj.pk).update(**fields)
    obj.refresh_from_db()


def test_downtime_full_cycle_inside_window(make_equipment, staff_user, engineer):
    now = timezone.now()
    eq = make_equipment(serial_number="SN-MRI", name="MRI", is_critical_asset=True)
    complaint = lodge_complaint(staff_user, eq, "coil fault")
    _backdate(complaint, created_at=now - timedelta(days=10))
    wo = start_repair(open_work_order(eq, engineer), engineer)
    wo = complete_work_order(wo, engineer, FaultCategory.ELECTRICAL)
    _backdate(wo, repair_completed_at=now - timedelta(days=8))
    result = metrics.critical_downtime_by_department(now - timedelta(days=30), now)
    assert result == {"ICU": pytest.approx(48.0, abs=0.1)}


def test_downtime_clipped_to_window(make_equipment, staff_user, engineer):
    now = timezone.now()
    eq = make_equipment(serial_number="SN-CT", is_critical_asset=True)
    complaint = lodge_complaint(staff_user, eq, "tube fault")
    _backdate(complaint, created_at=now - timedelta(days=40))
    wo = start_repair(open_work_order(eq, engineer), engineer)
    wo = complete_work_order(wo, engineer, FaultCategory.OTHER)
    _backdate(wo, repair_completed_at=now - timedelta(days=29))
    result = metrics.critical_downtime_by_department(now - timedelta(days=30), now)
    assert result["ICU"] == pytest.approx(24.0, abs=0.1)


def test_non_critical_equipment_excluded(equipment, staff_user, engineer):
    now = timezone.now()
    lodge_complaint(staff_user, equipment, "broken")  # equipment fixture: not critical
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, FaultCategory.OTHER)
    assert metrics.critical_downtime_by_department(
        now - timedelta(days=30), timezone.now()) == {}


def test_per_engineer_activity_counts_participation(
        equipment, staff_user, engineer, engineer2):
    now = timezone.now()
    lodge_complaint(staff_user, equipment, "broken")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer2, FaultCategory.MECHANICAL,
                        participants=[engineer])
    extra = lodge_complaint(staff_user, equipment, "hmm")
    close_complaint(extra, engineer, CloseReason.NO_FAULT, close_note="fine")
    rows = {r["employee_id"]: r for r in
            metrics.per_engineer_activity(now - timedelta(days=1), timezone.now())}
    assert rows["EMP-100"]["repairs"] == 1       # participant
    assert rows["EMP-101"]["repairs"] == 1       # closer, auto-participant
    assert rows["EMP-100"]["complaints_closed"] == 1


def test_fault_categories_and_counts(equipment, engineer):
    now = timezone.now()
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    complete_work_order(wo, engineer, FaultCategory.BATTERY_POWER)
    counts = metrics.fault_category_counts(now - timedelta(days=1), timezone.now())
    assert counts == {"Battery / Power": 1}
    assert metrics.repairs_completed_count(now - timedelta(days=1), timezone.now()) == 1


def test_delayed_repairs_listed(equipment, engineer):
    now = timezone.now()
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    add_remark(wo, engineer, "waiting for vendor part", kind="delay")
    rows = metrics.delayed_repairs(now - timedelta(days=1), timezone.now())
    assert len(rows) == 1
    assert rows[0]["wo_id"] == wo.pk
    assert "vendor part" in rows[0]["latest_delay_note"]
