import pytest

from apps.core.exceptions import InvalidTransition
from apps.core.models import AuditLog
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import condemn_equipment
from apps.maintenance.models import (
    CloseReason, ComplaintStatus, RemarkKind, WorkOrderOutcome, WorkOrderStatus,
)
from apps.maintenance.services import lodge_complaint, open_work_order, start_repair

pytestmark = pytest.mark.django_db


def test_condemn_working_equipment(equipment, engineer):
    condemn_equipment(equipment, engineer, remark="beyond repair",
                      condemned_location="Store Room B")
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.CONDEMNED
    assert equipment.condemned_at is not None
    assert equipment.condemned_location == "Store Room B"
    assert AuditLog.objects.filter(verb="equipment.condemned").exists()


def test_condemn_cascades_to_workorder_and_complaints(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "sparks and smoke")
    wo = start_repair(open_work_order(equipment, engineer), engineer)
    condemn_equipment(equipment, engineer, remark="unsafe",
                      condemned_location="Disposal yard")
    equipment.refresh_from_db(); wo.refresh_from_db(); complaint.refresh_from_db()
    assert equipment.status == EquipmentStatus.CONDEMNED
    assert wo.status == WorkOrderStatus.COMPLETED
    assert wo.outcome == WorkOrderOutcome.CONDEMNED
    assert wo.closed_by == engineer
    assert wo.remarks.filter(kind=RemarkKind.SYSTEM, text__icontains="condemned").exists()
    assert complaint.status == ComplaintStatus.CLOSED
    assert complaint.close_reason == CloseReason.RESOLVED
    assert "condemned" in complaint.close_note.lower()


def test_cannot_condemn_twice(equipment, engineer):
    condemn_equipment(equipment, engineer, remark="done", condemned_location="Store")
    equipment.refresh_from_db()
    with pytest.raises(InvalidTransition):
        condemn_equipment(equipment, engineer, remark="again", condemned_location="Store")


def test_no_complaints_after_condemnation(equipment, staff_user, engineer):
    from apps.core.exceptions import ComplaintNotAllowed
    condemn_equipment(equipment, engineer, remark="done", condemned_location="Store")
    equipment.refresh_from_db()
    with pytest.raises(ComplaintNotAllowed):
        lodge_complaint(staff_user, equipment, "still want to report")
