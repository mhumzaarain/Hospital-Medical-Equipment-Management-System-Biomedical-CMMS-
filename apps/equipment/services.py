from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core import audit
from apps.core.exceptions import InvalidTransition

from .models import Equipment, EquipmentStatus, StatusEvent

ALLOWED_TRANSITIONS = {
    EquipmentStatus.WORKING: {EquipmentStatus.IN_REPAIR, EquipmentStatus.CONDEMNED},
    EquipmentStatus.IN_REPAIR: {EquipmentStatus.WORKING, EquipmentStatus.CONDEMNED},
    EquipmentStatus.CONDEMNED: set(),
}


def _require_engineer_or_admin(actor):
    if not actor.is_engineer_or_admin:
        raise PermissionDenied("Only engineers or admins may do this.")


@transaction.atomic
def transition_status(equipment, new_status, actor, remark="", work_order=None):
    """The single choke point for equipment status. Nothing else writes
    Equipment.status. `work_order` is accepted now but only persisted from
    Task 6 onward (the StatusEvent.work_order column arrives there)."""
    _require_engineer_or_admin(actor)
    equipment = Equipment.objects.select_for_update().get(pk=equipment.pk)
    old_status = equipment.status
    if new_status not in ALLOWED_TRANSITIONS[old_status]:
        raise InvalidTransition(f"Cannot go from {old_status} to {new_status}.")
    equipment.status = new_status
    equipment.save(update_fields=["status"])
    event = StatusEvent.objects.create(
        equipment=equipment,
        old_status=old_status,
        new_status=new_status,
        actor=actor,
        remark=remark,
        work_order=work_order,
    )
    audit.record(
        actor,
        "equipment.status_changed",
        equipment,
        {"old": old_status, "new": new_status, "remark": remark},
    )
    return event


@transaction.atomic
def condemn_equipment(equipment, actor, remark, condemned_location):
    """Terminal lifecycle step. Cascades in one transaction (spec section 6)."""
    from django.utils import timezone

    from apps.maintenance.models import (
        ACTIVE_WORKORDER_STATUSES,
        CloseReason,
        ComplaintStatus,
        Remark,
        RemarkKind,
        WorkOrderOutcome,
        WorkOrderStatus,
    )
    from apps.maintenance.services import close_complaint

    transition_status(equipment, EquipmentStatus.CONDEMNED, actor, remark=remark)
    equipment.refresh_from_db()
    equipment.condemned_at = timezone.now()
    equipment.condemned_location = condemned_location
    equipment.save(update_fields=["condemned_at", "condemned_location"])

    active_wo = equipment.work_orders.filter(
        status__in=ACTIVE_WORKORDER_STATUSES
    ).first()
    if active_wo:
        now = timezone.now()
        active_wo.status = WorkOrderStatus.COMPLETED
        active_wo.outcome = WorkOrderOutcome.CONDEMNED
        active_wo.repair_completed_at = active_wo.repair_completed_at or now
        active_wo.closed_by = actor
        active_wo.closed_at = now
        active_wo.save(
            update_fields=[
                "status",
                "outcome",
                "repair_completed_at",
                "closed_by",
                "closed_at",
            ]
        )
        Remark.objects.create(
            work_order=active_wo,
            author=actor,
            kind=RemarkKind.SYSTEM,
            text="Device condemned; work order closed automatically.",
        )

    for complaint in equipment.complaints.exclude(status=ComplaintStatus.CLOSED):
        close_complaint(
            complaint, actor, CloseReason.RESOLVED, close_note="Device condemned."
        )

    audit.record(
        actor,
        "equipment.condemned",
        equipment,
        {"remark": remark, "location": condemned_location},
    )
    return equipment


@transaction.atomic
def create_equipment(actor, **fields):
    _require_engineer_or_admin(actor)
    equipment = Equipment.objects.create(**fields)
    audit.record(
        actor,
        "equipment.created",
        equipment,
        {"serial_number": equipment.serial_number},
    )
    return equipment


@transaction.atomic
def update_equipment(equipment, actor, **fields):
    _require_engineer_or_admin(actor)
    changes = {}
    for name, value in fields.items():
        old = getattr(equipment, name)
        if old != value:
            changes[name] = {"old": str(old), "new": str(value)}
            setattr(equipment, name, value)
    if changes:
        equipment.save(update_fields=list(changes.keys()))
        audit.record(actor, "equipment.updated", equipment, changes)
    return equipment
