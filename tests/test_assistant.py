import pytest

from apps.ai import assistant, client
from apps.ai.models import AssistantMessage, ManualChunk, ServiceManual
from apps.maintenance.models import Complaint


@pytest.fixture
def manual(db, engineer):
    manual = ServiceManual.objects.create(
        manufacturer="Hamilton", model_number="C2",
        title="C2 Manual", uploaded_by=engineer, status="ready",
    )
    from django.contrib.postgres.search import SearchVector

    ManualChunk.objects.create(
        manual=manual, page_start=42, page_end=42,
        text="NO OXYGEN alarm: check the O2 supply line for blockage.",
    )
    manual.chunks.update(search=SearchVector("text"))
    return manual


def test_build_messages_includes_all_blocks(
    equipment, make_work_order, engineer, manual, db
):
    wo = make_work_order()
    Complaint.objects.create(
        equipment=equipment, reporter=engineer, work_order=wo,
        description="no oxygen error on screen",
    )
    messages = assistant.build_messages(equipment, wo, "what should I check?")
    user_block = messages[-1]["content"]
    assert "Hamilton" in user_block                      # device card
    assert "no oxygen error on screen" in user_block     # WO complaint context
    assert "p. 42" in user_block                         # manual citation
    assert messages[0]["role"] == "system"
    assert "advisory" in messages[0]["content"].lower()


def test_build_messages_without_manual_says_so(equipment, db):
    messages = assistant.build_messages(equipment, None, "hello?")
    assert "No service manual" in messages[-1]["content"]


def test_answer_saves_assistant_reply(equipment, engineer, monkeypatch, db):
    monkeypatch.setattr(client, "chat", lambda m, **kw: "Check the O2 line.")
    question = AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="user", content="no oxygen error"
    )
    reply = assistant.answer(question.id)
    assert reply.role == "assistant" and reply.content == "Check the O2 line."
    assert reply.equipment == equipment


def test_answer_failure_writes_unavailable_message(
    equipment, engineer, monkeypatch, db
):
    def _boom(m, **kw):
        raise client.LLMUnavailable("down")

    monkeypatch.setattr(client, "chat", _boom)
    question = AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="user", content="hi"
    )
    reply = assistant.answer(question.id)
    assert "not available" in reply.content


def test_answer_uses_interactive_mode(equipment, engineer, monkeypatch, db):
    seen = {}

    def _chat(messages, **kwargs):
        seen.update(kwargs)
        return "ok"

    monkeypatch.setattr(client, "chat", _chat)
    question = AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="user", content="hi"
    )
    assistant.answer(question.id)
    assert seen.get("interactive") is True
