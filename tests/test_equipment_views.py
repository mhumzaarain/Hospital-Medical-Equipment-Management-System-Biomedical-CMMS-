import pytest
from django.urls import reverse

from apps.equipment.models import Equipment, EquipmentStatus

pytestmark = pytest.mark.django_db


def test_staff_sees_registry_readonly(client, staff_user, equipment):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_list"))
    assert response.status_code == 200
    assert b"SN-0001" in response.content


def test_staff_cannot_open_create_page(client, staff_user):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_create"))
    assert response.status_code == 403


def test_engineer_creates_equipment(client, engineer, department):
    client.force_login(engineer)
    response = client.post(
        reverse("equipment_create"),
        {
            "name": "Infusion Pump",
            "manufacturer": "B.Braun",
            "vendor": "MedServe",
            "model_number": "P7",
            "serial_number": "SN-0100",
            "department": department.pk,
            "is_critical_asset": "",
        },
    )
    assert response.status_code == 302
    assert Equipment.objects.filter(serial_number="SN-0100").exists()


def test_search_partial_matches_serial(client, staff_user, equipment):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_search"), {"q": "SN-0001"})
    assert response.status_code == 200
    assert b"SN-0001" in response.content


def test_search_can_exclude_unavailable(
    client, staff_user, engineer, equipment, make_equipment
):
    from apps.equipment.services import transition_status

    broken = make_equipment(serial_number="SN-0002")
    transition_status(broken, EquipmentStatus.IN_REPAIR, engineer)
    client.force_login(staff_user)
    response = client.get(
        reverse("equipment_search"), {"q": "SN-000", "exclude_unavailable": "1"}
    )
    assert b"SN-0001" in response.content
    assert b"SN-0002" not in response.content


def test_condemn_via_view(client, engineer, equipment):
    client.force_login(engineer)
    response = client.post(
        reverse("equipment_condemn", args=[equipment.pk]),
        {
            "remark": "beyond economical repair",
            "condemned_location": "Store Room B",
        },
    )
    assert response.status_code == 302
    equipment.refresh_from_db()
    assert equipment.status == EquipmentStatus.CONDEMNED


def test_detail_shows_status_history(client, engineer, equipment):
    from apps.equipment.services import transition_status

    transition_status(equipment, EquipmentStatus.IN_REPAIR, engineer, remark="checking")
    client.force_login(engineer)
    response = client.get(reverse("equipment_detail", args=[equipment.pk]))
    assert response.status_code == 200
    assert b"checking" in response.content
