"""All Procrastinate tasks that touch the LLM live in this app (spec §2)."""

from procrastinate.contrib.django import app


@app.periodic(cron="0 3 * * 1")
@app.task(name="ai.compute_risk_scores", retry=3)
def compute_risk_scores(timestamp=None):
    from django.utils import timezone

    from apps.equipment.models import Equipment, EquipmentStatus

    from .models import RiskScoringConfig
    from .services import assess_equipment

    now = timezone.now()
    config = RiskScoringConfig.get()
    for equipment in Equipment.objects.exclude(status=EquipmentStatus.CONDEMNED):
        assess_equipment(equipment, config, now)
