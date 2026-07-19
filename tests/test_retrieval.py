import pytest
from django.utils import timezone

from apps.ai import manuals, retrieval
from apps.ai.models import ServiceManual
from apps.maintenance.models import Complaint, Remark, WorkOrderStatus


@pytest.fixture
def indexed_manual(db, engineer, monkeypatch):
    manual = ServiceManual.objects.create(
        manufacturer="Hamilton", model_number="C2",
        title="C2 Manual", uploaded_by=engineer,
    )
    pages = [
        "Chapter 1: routine cleaning and calibration schedules. " * 30,
        "NO OXYGEN alarm: check the O2 supply line for blockage. " * 30,
    ]
    monkeypatch.setattr(manuals, "extract_pages", lambda f: pages)
    manuals.process(manual)
    return manual


def test_manual_sections_finds_relevant_page(indexed_manual):
    sections = retrieval.manual_sections(indexed_manual, "no oxygen alarm")
    assert sections
    assert "NO OXYGEN" in sections[0].text


def test_manual_sections_or_fallback(indexed_manual):
    # websearch ANDs terms; this phrase only matches via the OR fallback
    sections = retrieval.manual_sections(indexed_manual, "oxygen gibberishword")
    assert sections and "O2" in sections[0].text


def test_similar_repairs_matches_same_model_history(
    equipment, make_equipment, make_work_order, engineer, db
):
    sibling = make_equipment(serial_number="SN-2")  # same Hamilton C2 model
    wo = make_work_order(
        eq=sibling, status=WorkOrderStatus.COMPLETED,
        repair_completed_at=timezone.now(), fault_category="electrical",
    )
    Complaint.objects.create(
        equipment=sibling, reporter=engineer, work_order=wo,
        description="ventilator shows no oxygen error",
    )
    Remark.objects.create(work_order=wo, author=engineer, text="replaced O2 cell")
    rows = retrieval.similar_repairs(equipment, "no oxygen error")
    assert rows and rows[0]["wo_id"] == wo.id
    assert "replaced O2 cell" in rows[0]["remarks"]


def test_similar_repairs_ignores_other_models(
    equipment, make_equipment, make_work_order, engineer, db
):
    other = make_equipment(serial_number="SN-3", model_number="G5")
    wo = make_work_order(
        eq=other, status=WorkOrderStatus.COMPLETED,
        repair_completed_at=timezone.now(),
    )
    Complaint.objects.create(
        equipment=other, reporter=engineer, work_order=wo,
        description="no oxygen error here too",
    )
    assert retrieval.similar_repairs(equipment, "no oxygen error") == []
