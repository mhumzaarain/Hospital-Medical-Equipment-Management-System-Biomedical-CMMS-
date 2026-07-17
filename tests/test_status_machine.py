import pytest
from django.core.exceptions import PermissionDenied

from apps.core.exceptions import InvalidTransition
from apps.core.models import AuditLog
from apps.equipment.models import EquipmentStatus, StatusEvent
from apps.equipment.services import transition_status

pytestmark = pytest.mark.django_db


def test_working_to_in_repair(equipment, engineer):
    event = transition_status(
        equipment, EquipmentStatus.IN_REPAIR, engineer, remark="starting"
    )
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.IN_REPAIR
    assert event.old_status == EquipmentStatus.WORKING
    assert event.new_status == EquipmentStatus.IN_REPAIR
    assert event.actor == engineer
    assert AuditLog.objects.filter(verb="equipment.status_changed").count() == 1


def test_in_repair_back_to_working(equipment, engineer):
    transition_status(equipment, EquipmentStatus.IN_REPAIR, engineer)
    equipment.refresh_from_db()
    transition_status(equipment, EquipmentStatus.WORKING, engineer)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.WORKING
    assert StatusEvent.objects.filter(equipment=equipment).count() == 2


def test_working_to_working_is_illegal(equipment, engineer):
    with pytest.raises(InvalidTransition):
        transition_status(equipment, EquipmentStatus.WORKING, engineer)


def test_condemned_is_terminal(equipment, engineer):
    transition_status(equipment, EquipmentStatus.CONDEMNED, engineer)
    equipment.refresh_from_db()
    for target in (EquipmentStatus.WORKING, EquipmentStatus.IN_REPAIR):
        with pytest.raises(InvalidTransition):
            transition_status(equipment, target, engineer)


def test_staff_cannot_transition(equipment, staff_user):
    with pytest.raises(PermissionDenied):
        transition_status(equipment, EquipmentStatus.IN_REPAIR, staff_user)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.WORKING
    assert StatusEvent.objects.count() == 0


def test_admin_can_transition(equipment, admin_user):
    transition_status(equipment, EquipmentStatus.IN_REPAIR, admin_user)
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.IN_REPAIR
