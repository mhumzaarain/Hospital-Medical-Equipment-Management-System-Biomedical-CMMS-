import pytest
from django.db import IntegrityError

from apps.equipment.models import Equipment, EquipmentStatus, StatusEvent

pytestmark = pytest.mark.django_db


def test_equipment_defaults(equipment):
    assert equipment.status == EquipmentStatus.WORKING
    assert equipment.is_critical_asset is False
    assert equipment.extra == {}


def test_serial_number_unique(equipment, make_equipment):
    with pytest.raises(IntegrityError):
        make_equipment(serial_number="SN-0001")


def test_equipment_can_never_be_deleted(equipment):
    with pytest.raises(TypeError):
        equipment.delete()
    with pytest.raises(TypeError):
        Equipment.objects.all().delete()


def test_status_event_is_append_only(equipment, engineer):
    event = StatusEvent.objects.create(
        equipment=equipment,
        old_status=EquipmentStatus.WORKING,
        new_status=EquipmentStatus.IN_REPAIR,
        actor=engineer,
        remark="test",
    )
    event.remark = "edited"
    with pytest.raises(TypeError):
        event.save()
    with pytest.raises(TypeError):
        event.delete()


def test_user_department_is_optional(staff_user, department):
    staff_user.department = department
    staff_user.save()
    staff_user.refresh_from_db()
    assert staff_user.department == department
