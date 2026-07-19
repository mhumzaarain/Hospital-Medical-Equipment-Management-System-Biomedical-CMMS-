import pytest
from django.urls import reverse

from apps.ai.models import AssistantMessage


@pytest.fixture
def engineer_client(client, engineer):
    client.force_login(engineer)
    return client


def test_staff_blocked(client, staff_user, equipment):
    client.force_login(staff_user)
    url = reverse("assistant_messages", args=[equipment.pk])
    assert client.get(url).status_code == 403


def test_send_creates_message_and_defers(
    engineer_client, engineer, equipment, make_work_order, monkeypatch
):
    deferred = []
    from apps.ai import tasks

    monkeypatch.setattr(
        tasks.answer_assistant_chat, "defer", lambda **kw: deferred.append(kw)
    )
    wo = make_work_order()
    url = reverse("assistant_send", args=[equipment.pk]) + f"?wo={wo.pk}"
    response = engineer_client.post(url, {"content": "no oxygen error"})
    assert response.status_code == 200
    message = AssistantMessage.objects.get()
    assert message.role == "user" and message.work_order == wo
    assert deferred == [{"message_id": message.id}]
    assert b"no oxygen error" in response.content


def test_poll_shows_thinking_until_answer(engineer_client, engineer, equipment):
    AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="user", content="hi"
    )
    url = reverse("assistant_messages", args=[equipment.pk])
    assert b"thinking" in engineer_client.get(url).content.lower()
    AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="assistant", content="Answer."
    )
    body = engineer_client.get(url).content
    assert b"Answer." in body and b"Advisory only" in body
