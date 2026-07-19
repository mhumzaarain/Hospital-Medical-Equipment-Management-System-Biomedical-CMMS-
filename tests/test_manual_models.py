import pytest

from apps.ai.models import AssistantMessage, ManualChunk, ServiceManual


@pytest.fixture
def manual(db, engineer):
    return ServiceManual.objects.create(
        manufacturer="Hamilton",
        model_number="C2",
        title="Hamilton C2 Service Manual",
        uploaded_by=engineer,
        status="ready",
    )


def test_for_equipment_matches_case_insensitively(manual, make_equipment):
    eq = make_equipment(manufacturer="HAMILTON", model_number="c2")
    assert ServiceManual.for_equipment(eq) == manual


def test_for_equipment_ignores_unready(manual, equipment):
    manual.status = "processing"
    manual.save()
    assert ServiceManual.for_equipment(equipment) is None


def test_unique_per_model(manual, engineer):
    with pytest.raises(Exception):
        ServiceManual.objects.create(
            manufacturer="Hamilton", model_number="C2",
            title="dupe", uploaded_by=engineer,
        )


def test_chunks_cascade_on_manual_delete(manual):
    ManualChunk.objects.create(manual=manual, text="x", page_start=1, page_end=1)
    manual.delete()
    assert ManualChunk.objects.count() == 0


def test_assistant_message_ordering(equipment, engineer, db):
    a = AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="user", content="first"
    )
    b = AssistantMessage.objects.create(
        equipment=equipment, user=engineer, role="assistant", content="second"
    )
    assert list(equipment.assistant_messages.all()) == [a, b]
