from datetime import timedelta

import pytest
from django.utils import timezone

from apps.ai import client, services
from apps.ai.models import RiskScoringConfig
from apps.maintenance.models import WorkOrderStatus


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def _chat(messages, **kwargs):
        calls.append(messages)
        return "Narrative text."

    monkeypatch.setattr(client, "chat", _chat)
    return calls


def _completed_wo(make_work_order, when):
    wo = make_work_order(
        status=WorkOrderStatus.COMPLETED, repair_completed_at=when
    )
    return wo


def test_score_counts_completed_repairs_in_window(
    equipment, make_work_order, db
):
    now = timezone.now()
    _completed_wo(make_work_order, now - timedelta(days=30))
    _completed_wo(make_work_order, now - timedelta(days=60))
    _completed_wo(make_work_order, now - timedelta(days=400))  # outside window
    config = RiskScoringConfig.get()
    score, factors = services.compute_score(equipment, config, now)
    assert score == 2
    assert factors["repairs_in_window"] == 2
    assert factors["window_months"] == 12


def test_points_per_repair_multiplies(equipment, make_work_order, db):
    now = timezone.now()
    _completed_wo(make_work_order, now - timedelta(days=10))
    config = RiskScoringConfig.get()
    config.points_per_repair = 5
    config.save()
    score, _ = services.compute_score(equipment, config, now)
    assert score == 5


def test_narrative_only_at_or_above_threshold(
    equipment, make_work_order, fake_llm, db
):
    now = timezone.now()
    for days in (10, 20, 40):
        _completed_wo(make_work_order, now - timedelta(days=days))
    assessment = services.assess_equipment(equipment, RiskScoringConfig.get(), now)
    assert assessment.score == 3
    assert assessment.narrative == "Narrative text."


def test_no_narrative_below_threshold(equipment, make_work_order, fake_llm, db):
    now = timezone.now()
    _completed_wo(make_work_order, now - timedelta(days=10))
    assessment = services.assess_equipment(equipment, RiskScoringConfig.get(), now)
    assert assessment.score == 1
    assert assessment.narrative is None
    assert fake_llm == []


def test_llm_failure_still_records_score(
    equipment, make_work_order, monkeypatch, db
):
    def _boom(messages, **kwargs):
        raise client.LLMUnavailable("down")

    monkeypatch.setattr(client, "chat", _boom)
    now = timezone.now()
    for days in (5, 15, 25):
        _completed_wo(make_work_order, now - timedelta(days=days))
    assessment = services.assess_equipment(equipment, RiskScoringConfig.get(), now)
    assert assessment.score == 3 and assessment.narrative is None


def test_high_risk_devices_lists_latest_per_device(
    make_equipment, make_work_order, fake_llm, db
):
    now = timezone.now()
    hot = make_equipment(serial_number="SN-HOT")
    cold = make_equipment(serial_number="SN-COLD")
    for days in (5, 15, 25):
        make_work_order(
            eq=hot, status=WorkOrderStatus.COMPLETED,
            repair_completed_at=now - timedelta(days=days),
        )
    config = RiskScoringConfig.get()
    services.assess_equipment(hot, config, now)
    services.assess_equipment(cold, config, now)
    rows = services.high_risk_devices()
    assert [a.equipment for a in rows] == [hot]
