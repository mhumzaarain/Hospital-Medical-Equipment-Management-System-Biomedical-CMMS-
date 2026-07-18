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
