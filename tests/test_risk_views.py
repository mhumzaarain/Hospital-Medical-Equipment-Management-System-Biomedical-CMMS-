import pytest
from django.urls import reverse

from apps.ai.models import RiskAssessment


@pytest.fixture
def assessment(equipment):
    return RiskAssessment.objects.create(
        equipment=equipment,
        score=4,
        factors={"repairs_in_window": 4, "window_months": 12,
                 "points_per_repair": 1, "high_risk_threshold": 3},
        narrative="Breaks a lot.",
    )


def test_equipment_detail_shows_risk_to_engineer(
    client, engineer, assessment, equipment
):
    client.force_login(engineer)
    response = client.get(reverse("equipment_detail", args=[equipment.pk]))
    assert b"High risk" in response.content
    assert b"Breaks a lot." in response.content


def test_equipment_detail_hides_risk_from_staff(
    client, staff_user, assessment, equipment
):
    client.force_login(staff_user)
    response = client.get(reverse("equipment_detail", args=[equipment.pk]))
    assert b"High risk" not in response.content


def test_dashboard_lists_high_risk_devices(client, engineer, assessment):
    client.force_login(engineer)
    response = client.get(reverse("dashboard"))
    assert assessment.equipment.serial_number.encode() in response.content
