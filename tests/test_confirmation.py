import pytest

from apps.maintenance.models import Complaint, FunctionalConfirmation
from apps.maintenance.models import CloseReason, ComplaintStatus, WorkOrderOutcome, WorkOrderStatus
from apps.maintenance.services import (
    complete_work_order, lodge_complaint, open_work_order, start_repair,
)
from apps.equipment.services import condemn_equipment
from apps.maintenance.models import FaultCategory

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
