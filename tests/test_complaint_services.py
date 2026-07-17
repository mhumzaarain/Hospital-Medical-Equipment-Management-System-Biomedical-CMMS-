import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import ComplaintNotAllowed, WorkOrderStateError
from apps.core.models import AuditLog
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import transition_status
from apps.maintenance.models import CloseReason, ComplaintStatus, WorkOrderStatus
from apps.maintenance.services import close_complaint, lodge_complaint

pytestmark = pytest.mark.django_db


def test_staff_can_lodge_complaint(equipment, staff_user):
    complaint = lodge_complaint(staff_user, equipment, "Screen goes black")
    assert complaint.status == ComplaintStatus.OPEN
    assert complaint.reporter == staff_user
    assert complaint.work_order is None
    assert AuditLog.objects.filter(verb="complaint.lodged").count() == 1


def test_complaint_blocked_when_in_repair(equipment, staff_user, engineer, make_work_order):
    wo = make_work_order(status=WorkOrderStatus.IN_PROGRESS)
    transition_status(equipment, EquipmentStatus.IN_REPAIR, engineer, work_order=wo)
    with pytest.raises(ComplaintNotAllowed) as exc:
        lodge_complaint(staff_user, equipment, "still broken")
    assert f"Work Order #{wo.pk}" in str(exc.value)


def test_complaint_blocked_when_condemned(equipment, staff_user, engineer):
    transition_status(equipment, EquipmentStatus.CONDEMNED, engineer)
    with pytest.raises(ComplaintNotAllowed):
        lodge_complaint(staff_user, equipment, "it is broken")


def test_complaint_auto_attaches_to_open_workorder(equipment, staff_user, make_work_order):
    wo = make_work_order(status=WorkOrderStatus.OPEN)
    complaint = lodge_complaint(staff_user, equipment, "second report")
    assert complaint.status == ComplaintStatus.ATTACHED
    assert complaint.work_order == wo


def test_engineer_closes_duplicate_with_link(equipment, staff_user, engineer):
    first = lodge_complaint(staff_user, equipment, "display broken")
    second = lodge_complaint(staff_user, equipment, "screen not working")
    closed = close_complaint(
        second, engineer, CloseReason.DUPLICATE,
        duplicate_of=first, close_note="already reported",
    )
    assert closed.status == ComplaintStatus.CLOSED
    assert closed.close_reason == CloseReason.DUPLICATE
    assert closed.duplicate_of == first
    assert closed.closed_by == engineer
    assert closed.closed_at is not None


def test_duplicate_close_requires_link_or_note(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    with pytest.raises(ValueError):
        close_complaint(complaint, engineer, CloseReason.DUPLICATE)


def test_staff_cannot_close_complaints(equipment, staff_user):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    with pytest.raises(PermissionDenied):
        close_complaint(complaint, staff_user, CloseReason.NO_FAULT)


def test_cannot_close_twice(equipment, staff_user, engineer):
    complaint = lodge_complaint(staff_user, equipment, "broken")
    close_complaint(complaint, engineer, CloseReason.NO_FAULT, close_note="tested ok")
    with pytest.raises(WorkOrderStateError):
        close_complaint(complaint, engineer, CloseReason.NO_FAULT)
