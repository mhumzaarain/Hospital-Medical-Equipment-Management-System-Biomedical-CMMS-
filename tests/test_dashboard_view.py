import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_dashboard_requires_engineer(client, staff_user):
    client.force_login(staff_user)
    assert client.get(reverse("dashboard")).status_code == 403


def test_dashboard_renders_for_engineer(client, engineer):
    client.force_login(engineer)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"chart.umd.js" in response.content
