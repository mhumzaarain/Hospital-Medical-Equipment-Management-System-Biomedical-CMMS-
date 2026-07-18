import pytest

from apps.ai.models import RiskAssessment, RiskScoringConfig


def test_config_singleton_defaults(db):
    config = RiskScoringConfig.get()
    assert (config.points_per_repair, config.high_risk_threshold) == (1, 3)
    assert RiskScoringConfig.get().pk == config.pk


def test_assessment_is_append_only(equipment, db):
    assessment = RiskAssessment.objects.create(
        equipment=equipment, score=2, factors={"repairs": 2}
    )
    assessment.score = 5
    with pytest.raises(TypeError):
        assessment.save()
    with pytest.raises(TypeError):
        assessment.delete()
