from django.conf import settings
from django.db import models

from apps.core.models import AppendOnlyModel, NoDeleteModel


class EquipmentStatus(models.TextChoices):
    WORKING = "working", "Working"
    IN_REPAIR = "in_repair", "In Repair"
    CONDEMNED = "condemned", "Condemned"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Equipment(NoDeleteModel):
    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=200)
    vendor = models.CharField(max_length=200, blank=True)
    model_number = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="equipment"
    )
    is_critical_asset = models.BooleanField(
        default=False,
        help_text="Downtime is tracked only for critical assets (MRI, CT, ...)",
    )
    purchase_date = models.DateField(null=True, blank=True)
    installation_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.WORKING
    )
    condemned_at = models.DateTimeField(null=True, blank=True)
    condemned_location = models.CharField(max_length=200, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name", "serial_number"]
        verbose_name_plural = "equipment"

    def __str__(self):
        return f"{self.name} {self.model_number} ({self.serial_number})"


class StatusEvent(AppendOnlyModel):
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name="status_events"
    )
    old_status = models.CharField(max_length=20, choices=EquipmentStatus.choices)
    new_status = models.CharField(max_length=20, choices=EquipmentStatus.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="status_events"
    )
    remark = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # work_order FK is added in Task 6 (maintenance app must exist first)

    class Meta:
        ordering = ["-created_at"]
