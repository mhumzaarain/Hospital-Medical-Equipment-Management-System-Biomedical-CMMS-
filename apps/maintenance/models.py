from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, NoDeleteModel
from apps.equipment.models import Equipment


class ComplaintStatus(models.TextChoices):
    OPEN = "open", "Open"
    ATTACHED = "attached", "Attached to Work Order"
    CLOSED = "closed", "Closed"


class CloseReason(models.TextChoices):
    RESOLVED = "resolved", "Resolved"
    DUPLICATE = "duplicate", "Duplicate"
    NO_FAULT = "no_fault", "No Fault Found"


class WorkOrderStatus(models.TextChoices):
    OPEN = "open", "Open"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class WorkOrderOutcome(models.TextChoices):
    REPAIRED = "repaired", "Repaired"
    CONDEMNED = "condemned", "Condemned"


class FaultCategory(models.TextChoices):
    ELECTRICAL = "electrical", "Electrical"
    BATTERY_POWER = "battery_power", "Battery / Power"
    DISPLAY_MONITOR = "display_monitor", "Display / Monitor"
    MECHANICAL = "mechanical", "Mechanical"
    CALIBRATION = "calibration", "Calibration"
    SOFTWARE = "software", "Software"
    ACCESSORY_PROBE = "accessory_probe", "Accessory / Probe"
    OTHER = "other", "Other"


class RemarkKind(models.TextChoices):
    NOTE = "note", "Note"
    DELAY = "delay", "Delay"
    SYSTEM = "system", "System"


ACTIVE_WORKORDER_STATUSES = (WorkOrderStatus.OPEN, WorkOrderStatus.IN_PROGRESS)


class WorkOrder(NoDeleteModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="work_orders"
    )
    status = models.CharField(
        max_length=20, choices=WorkOrderStatus.choices, default=WorkOrderStatus.OPEN
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="workorders_opened",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    repair_started_at = models.DateTimeField(null=True, blank=True)
    repair_completed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="workorders_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(
        max_length=20, choices=WorkOrderOutcome.choices, null=True, blank=True
    )
    fault_category = models.CharField(
        max_length=30, choices=FaultCategory.choices, null=True, blank=True,
        help_text="Required when completing a repair.",
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="workorders_participated",
        help_text="Engineers who worked on this repair.",
    )

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["equipment"],
                condition=~models.Q(
                    status__in=[WorkOrderStatus.COMPLETED, WorkOrderStatus.CANCELLED]
                ),
                name="one_active_workorder_per_equipment",
            )
        ]

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_WORKORDER_STATUSES

    def __str__(self):
        return f"WO #{self.pk} — {self.equipment}"


class Complaint(NoDeleteModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="complaints"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="complaints_reported",
    )
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=ComplaintStatus.choices, default=ComplaintStatus.OPEN
    )
    work_order = models.ForeignKey(
        WorkOrder, null=True, blank=True, on_delete=models.PROTECT,
        related_name="complaints",
    )
    close_reason = models.CharField(
        max_length=20, choices=CloseReason.choices, null=True, blank=True
    )
    duplicate_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT,
        related_name="duplicates",
    )
    close_note = models.TextField(blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
        related_name="complaints_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Complaint #{self.pk} — {self.equipment}"


class Remark(AppendOnlyModel):
    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.PROTECT, related_name="remarks"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="remarks"
    )
    text = models.TextField()
    kind = models.CharField(
        max_length=10, choices=RemarkKind.choices, default=RemarkKind.NOTE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
