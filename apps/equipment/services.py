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
        equipment=equipment, old_status=old_status, new_status=new_status,
        actor=actor, remark=remark,
    )
    audit.record(actor, "equipment.status_changed", equipment,
                 {"old": old_status, "new": new_status, "remark": remark})
    return event
