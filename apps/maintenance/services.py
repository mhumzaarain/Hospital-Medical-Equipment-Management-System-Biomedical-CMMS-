from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.exceptions import ComplaintNotAllowed, WorkOrderStateError
from apps.equipment.models import EquipmentStatus
from apps.equipment.services import _require_engineer_or_admin

from .models import (
    ACTIVE_WORKORDER_STATUSES, CloseReason, Complaint, ComplaintStatus,
    WorkOrderStatus,
)


@transaction.atomic
def lodge_complaint(reporter, equipment, description) -> Complaint:
    equipment.refresh_from_db()
    if equipment.status == EquipmentStatus.CONDEMNED:
        raise ComplaintNotAllowed("This equipment is condemned; complaints are closed.")
    if equipment.status == EquipmentStatus.IN_REPAIR:
        active = equipment.work_orders.filter(
            status__in=ACTIVE_WORKORDER_STATUSES
        ).first()
        wo_ref = f"Work Order #{active.pk}" if active else "a work order"
        raise ComplaintNotAllowed(
            f"This equipment is already under repair ({wo_ref})."
        )
    open_wo = equipment.work_orders.filter(status=WorkOrderStatus.OPEN).first()
    complaint = Complaint.objects.create(
        equipment=equipment,
        reporter=reporter,
        description=description,
        status=ComplaintStatus.ATTACHED if open_wo else ComplaintStatus.OPEN,
        work_order=open_wo,
    )
    audit.record(reporter, "complaint.lodged", complaint,
                 {"equipment": equipment.serial_number,
                  "attached_to": open_wo.pk if open_wo else None})
    return complaint


@transaction.atomic
def close_complaint(complaint, actor, close_reason,
                    duplicate_of=None, close_note="") -> Complaint:
    _require_engineer_or_admin(actor)
    if complaint.status == ComplaintStatus.CLOSED:
        raise WorkOrderStateError("This complaint is already closed.")
    if close_reason == CloseReason.DUPLICATE and not (duplicate_of or close_note):
        raise ValueError(
            "Closing as duplicate requires the original complaint or a note."
        )
    complaint.status = ComplaintStatus.CLOSED
    complaint.close_reason = close_reason
    complaint.duplicate_of = duplicate_of
    complaint.close_note = close_note
    complaint.closed_by = actor
    complaint.closed_at = timezone.now()
    complaint.save(update_fields=[
        "status", "close_reason", "duplicate_of", "close_note",
        "closed_by", "closed_at",
    ])
    audit.record(actor, "complaint.closed", complaint,
                 {"reason": close_reason, "duplicate_of":
                  duplicate_of.pk if duplicate_of else None, "note": close_note})
    return complaint
