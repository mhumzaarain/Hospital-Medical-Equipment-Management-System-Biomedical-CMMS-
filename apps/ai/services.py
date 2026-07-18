from datetime import timedelta

from apps.equipment.models import Equipment, EquipmentStatus
from apps.maintenance.models import Complaint, Remark, WorkOrder, WorkOrderStatus

from . import client, prompts
from .models import RISK_WINDOW_MONTHS, RiskAssessment


def _window_start(now):
    return now - timedelta(days=RISK_WINDOW_MONTHS * 30)


def compute_score(equipment, config, now):
    repairs = WorkOrder.objects.filter(
        equipment=equipment,
        status=WorkOrderStatus.COMPLETED,
        repair_completed_at__gte=_window_start(now),
    ).count()
    factors = {
        "repairs_in_window": repairs,
        "window_months": RISK_WINDOW_MONTHS,
        "points_per_repair": config.points_per_repair,
        "high_risk_threshold": config.high_risk_threshold,
    }
    return repairs * config.points_per_repair, factors


def assess_equipment(equipment, config, now) -> RiskAssessment:
    score, factors = compute_score(equipment, config, now)
    narrative = None
    if score >= config.high_risk_threshold:
        recent_complaints = Complaint.objects.filter(
            equipment=equipment, created_at__gte=_window_start(now)
        ).order_by("-created_at")[:5]
        recent_remarks = Remark.objects.filter(
            work_order__equipment=equipment, created_at__gte=_window_start(now)
        ).order_by("-created_at")[:5]
        try:
            narrative = client.chat(
                prompts.risk_narrative_prompt(
                    equipment, factors, recent_complaints, recent_remarks
                )
            )
        except client.LLMUnavailable:
            narrative = None
    return RiskAssessment.objects.create(
        equipment=equipment, score=score, factors=factors, narrative=narrative
    )


def latest_assessment(equipment):
    return equipment.risk_assessments.order_by("-generated_at").first()


def high_risk_devices(limit=10):
    rows = []
    for equipment in Equipment.objects.exclude(status=EquipmentStatus.CONDEMNED):
        assessment = latest_assessment(equipment)
        if (
            assessment
            and assessment.score
            >= assessment.factors.get("high_risk_threshold", 0)
        ):
            rows.append(assessment)
    rows.sort(key=lambda a: -a.score)
    return rows[:limit]
