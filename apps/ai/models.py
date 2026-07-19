from django.db import models

from apps.core.models import AppendOnlyModel
from apps.equipment.models import Equipment

RISK_WINDOW_MONTHS = 12  # fixed design constant — deliberately not in config


class RiskScoringConfig(models.Model):
    """Singleton. Exactly two admin-editable numbers (spec §4)."""

    points_per_repair = models.PositiveIntegerField(default=1)
    high_risk_threshold = models.PositiveIntegerField(default=3)

    class Meta:
        verbose_name = "risk scoring configuration"

    @classmethod
    def get(cls) -> "RiskScoringConfig":
        config, _ = cls.objects.get_or_create(pk=1)
        return config

    def __str__(self):
        return (
            f"{self.points_per_repair} point(s)/repair, "
            f"high-risk at {self.high_risk_threshold}"
        )


class RiskAssessment(AppendOnlyModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="risk_assessments"
    )
    score = models.IntegerField()
    factors = models.JSONField(default=dict)
    narrative = models.TextField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"{self.equipment} score={self.score} @ {self.generated_at:%Y-%m-%d}"
