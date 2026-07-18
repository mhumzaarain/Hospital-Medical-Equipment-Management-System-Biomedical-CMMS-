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


def test_queue_rows_text_filter(client, engineer, staff_user, make_equipment):
    from apps.maintenance.services import lodge_complaint

    eq1 = make_equipment(serial_number="SN-AAA")
    eq2 = make_equipment(serial_number="SN-BBB")
    lodge_complaint(staff_user, eq1, "screen flickers")
    lodge_complaint(staff_user, eq2, "no power")
    client.force_login(engineer)
    response = client.get(reverse("complaint_queue_rows"), {"q": "flickers"})
    assert b"SN-AAA" in response.content
    assert b"SN-BBB" not in response.content


def test_queue_rows_unassigned_filter(client, engineer, staff_user, equipment):
    from apps.maintenance.services import lodge_complaint, open_work_order

    lodge_complaint(staff_user, equipment, "no power")
    open_work_order(equipment, engineer)
    client.force_login(engineer)
    response = client.get(reverse("complaint_queue_rows"), {"state": "unassigned"})
    assert b"no power" not in response.content


def test_complaint_age_hours(staff_user, equipment):
    from apps.maintenance.services import lodge_complaint

    c = lodge_complaint(staff_user, equipment, "no power")
    assert 0 <= c.age_hours < 1


def test_equipment_working_percent(make_equipment):
    from apps.reports import metrics

    make_equipment(serial_number="SN-W1", status="working")
    make_equipment(serial_number="SN-W2", status="working")
    make_equipment(serial_number="SN-R1", status="in_repair")
    make_equipment(serial_number="SN-C1", status="condemned")
    assert metrics.equipment_working_percent() == 67  # 2 of 3 non-condemned


def test_equipment_working_percent_empty(db):
    from apps.reports import metrics

    assert metrics.equipment_working_percent() is None


def test_dashboard_kpi_context(client, engineer):
    client.force_login(engineer)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    for key in ("working_percent", "downtime_hours", "repairs_delta", "downtime_delta"):
        assert key in response.context
