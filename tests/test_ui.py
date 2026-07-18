import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_sidebar_marks_active_nav(client, engineer):
    client.force_login(engineer)
    response = client.get(reverse("equipment_list"))
    assert b"nav-link-active" in response.content


def test_messages_rendered_as_toast_payload(client, engineer, equipment):
    client.force_login(engineer)
    response = client.post(
        reverse("workorder_open", args=[equipment.pk]), follow=True
    )
    assert b"window.djangoMessages" in response.content


def test_equipment_list_htmx_returns_rows_partial(client, engineer, equipment):
    client.force_login(engineer)
    response = client.get(reverse("equipment_list"), HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert b"<html" not in response.content
    assert b"SN-0001" in response.content


def test_equipment_list_htmx_status_filter(client, engineer, make_equipment):
    make_equipment(serial_number="SN-OK", status="working")
    make_equipment(serial_number="SN-BAD", status="in_repair")
    client.force_login(engineer)
    response = client.get(
        reverse("equipment_list"), {"status": "in_repair"}, HTTP_HX_REQUEST="true"
    )
    assert b"SN-BAD" in response.content
    assert b"SN-OK" not in response.content
